# AI-generated with Claude Code (Opus 5.5), 2026-11-20; reviewed by Jaehyuk Choi.
# Modified with Claude Code (Opus 5.5), 2026-11-26: crash, ANR and cooking events.
# Modified with Claude Code (Opus 5.5), 2026-11-27: video plays and favorites.
"""Usage events and request records (research/decisions/adr-007-telemetry.md)."""

import json
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.telemetry.sink import JsonlSink, build_telemetry_sink
from tests.conftest import StubVision

INSTALL = "0f8fad5b-d9cb-469f-a165-70867728950e"
SESSION = "7c9e6679-7425-40de-944b-e07fc1f90ae7"


class ListSink:
    def __init__(self) -> None:
        self.records: list[dict[str, Any]] = []

    def write(self, records: list[dict[str, Any]]) -> None:
        self.records.extend(records)


class SinkContract:
    """Every sink keeps the records in order and never raises."""

    def make(self, tmp_path) -> Any:
        raise NotImplementedError

    def read(self, sink, tmp_path) -> list[dict[str, Any]]:
        raise NotImplementedError

    def test_keeps_records_in_order(self, tmp_path):
        sink = self.make(tmp_path)
        sink.write([{"n": 1}, {"n": 2}])
        sink.write([])
        sink.write([{"n": 3}])
        assert [r["n"] for r in self.read(sink, tmp_path)] == [1, 2, 3]


class TestListSink(SinkContract):
    def make(self, tmp_path):
        return ListSink()

    def read(self, sink, tmp_path):
        return sink.records


class TestJsonlSink(SinkContract):
    def make(self, tmp_path):
        return JsonlSink(tmp_path / "usage.jsonl")

    def read(self, sink, tmp_path):
        lines = (tmp_path / "usage.jsonl").read_text(encoding="utf-8").splitlines()
        return [json.loads(line) for line in lines]

    def test_file_is_owner_only(self, tmp_path):
        JsonlSink(tmp_path / "usage.jsonl").write([{"n": 1}])
        assert (tmp_path / "usage.jsonl").stat().st_mode & 0o777 == 0o600

    def test_unwritable_path_is_swallowed(self, tmp_path):
        JsonlSink(tmp_path / "missing-dir" / "usage.jsonl").write([{"n": 1}])  # no exception


def batch(**event: Any) -> dict[str, Any]:
    return {
        "install_id": INSTALL,
        "session_id": SESSION,
        "app_version": "1.0",
        "events": [{"name": "dish_open", "t": 1, "dish_id": "kimchi-fried-rice", **event}],
    }


def test_events_are_stored_with_install_session_and_version():
    sink = ListSink()
    client = TestClient(create_app(StubVision(), telemetry=sink))
    response = client.post("/telemetry/events", json=batch())
    assert response.status_code == 202 and response.json() == {"accepted": 1}
    [record] = [r for r in sink.records if r["kind"] == "app"]
    assert record["install"] == INSTALL and record["session"] == SESSION
    assert record["name"] == "dish_open" and record["dish_id"] == "kimchi-fried-rice"
    assert "count" not in record  # unset fields are not stored


@pytest.mark.parametrize(
    "bad",
    [
        {"name": "ingredient_typed"},  # not one of the closed names
        {"note": "양파 두부"},  # no free-text field exists
        {"dish_id": "김치볶음밥"},  # ids only
        {"status": "whatever"},
        {"count": -1},
    ],
)
def test_anything_outside_the_closed_schema_is_refused(bad):
    sink = ListSink()
    client = TestClient(create_app(StubVision(), telemetry=sink))
    assert client.post("/telemetry/events", json=batch(**bad)).status_code == 422
    assert [r for r in sink.records if r["kind"] == "app"] == []


CRASH = {
    "name": "crash",
    "t": 1,
    "exception.type": "java.lang.IllegalStateException",
    "exception.cause.type": "java.io.IOException",
    "code.function.name": "com.example.mylittlechef.viewmodel.DishViewModel$load$1.invokeSuspend",
    "code.line.number": 251,
    "device.model.identifier": "SM-S918N",
    "android.os.api_level": 34,
    "count": 1,
}


def test_a_crash_is_stored_under_opentelemetry_names():
    sink = ListSink()
    client = TestClient(create_app(StubVision(), telemetry=sink))
    event = CRASH | {"device.model.identifier": "Pixel 7 Pro", "code.function.name": "a.B.<init>"}
    assert client.post("/telemetry/events", json=batch() | {"events": [event]}).status_code == 202
    [record] = [r for r in sink.records if r["kind"] == "app"]
    assert record["name"] == "crash"
    assert record["exception.type"] == "java.lang.IllegalStateException"
    assert record["code.line.number"] == 251 and record["android.os.api_level"] == 34
    assert record["device.model.identifier"] == "Pixel 7 Pro"
    assert not any(k.startswith(("exception_", "code_", "device_", "api_")) for k in record)


@pytest.mark.parametrize(
    "bad",
    [
        {"exception.message": "Unable to parse 양파"},  # never accepted
        {"exception.stacktrace": "at Foo.bar(Foo.kt:12)"},
        {"exception_type": "java.lang.Exception"},  # Python names are not wire names
        {"exception.type": "java.lang.Exception: 양파 두부"},  # a message glued to the class
        {"code.function.name": "Foo.bar(Foo.kt:12)"},  # a raw stack line
        {"code.function.name": "a" * 201},
        {"code.line.number": -1},
        {"device.model.identifier": "홍길동의 폰"},  # a phone name set by its owner
        {"android.os.api_level": 0},
        {"error": "java.lang.Exception"},  # the first draft's names are gone
    ],
)
def test_crash_fields_hold_names_only(bad):
    client = TestClient(create_app(StubVision(), telemetry=ListSink()))
    body = batch() | {"events": [CRASH | bad]}
    assert client.post("/telemetry/events", json=body).status_code == 422


def test_an_anr_and_a_native_crash_carry_the_phone_only():
    sink = ListSink()
    client = TestClient(create_app(StubVision(), telemetry=sink))
    phone = {"device.model.identifier": "SM-S918N", "android.os.api_level": 34}
    anr = {"name": "anr", "t": 5} | phone
    native = {"name": "crash", "t": 6, "exception.type": "native"} | phone
    body = batch() | {"events": [anr, native]}
    assert client.post("/telemetry/events", json=body).status_code == 202
    assert [r["name"] for r in sink.records if r["kind"] == "app"] == ["anr", "crash"]
    bad = anr | {"description": "Input dispatching timed out"}
    assert client.post("/telemetry/events", json=batch() | {"events": [bad]}).status_code == 422


def test_cooking_events_carry_the_recipe_kind_and_steps():
    sink = ListSink()
    client = TestClient(create_app(StubVision(), telemetry=sink))
    dish = {"dish_id": "kimchi-fried-rice"}
    events = [
        {"name": "cook_start", "t": 1, "recipe": "original", "steps": 6} | dish,
        {"name": "cook_exit", "t": 2, "recipe": "original", "count": 3, "steps": 6} | dish,
        {"name": "cook_complete", "t": 3, "recipe": "revised", "steps": 5, "duration_ms": 9} | dish,
    ]
    assert client.post("/telemetry/events", json=batch() | {"events": events}).status_code == 202
    stored = [r for r in sink.records if r["kind"] == "app"]
    assert [(r["name"], r["recipe"]) for r in stored] == [
        ("cook_start", "original"),
        ("cook_exit", "original"),
        ("cook_complete", "revised"),
    ]
    for bad in ({"recipe": "ai"}, {"steps": 501}, {"steps": -1}):
        body = batch() | {"events": [events[0] | bad]}
        assert client.post("/telemetry/events", json=body).status_code == 422


def test_video_plays_and_favorites_carry_a_dish_id_only():
    sink = ListSink()
    client = TestClient(create_app(StubVision(), telemetry=sink))
    names = ["video_play", "favorite_add", "favorite_remove"]
    events = [{"name": n, "t": i, "dish_id": "kimchi-fried-rice"} for i, n in enumerate(names)]
    assert client.post("/telemetry/events", json=batch() | {"events": events}).status_code == 202
    stored = [r for r in sink.records if r["kind"] == "app"]
    assert [(r["name"], r["dish_id"]) for r in stored] == [(n, "kimchi-fried-rice") for n in names]
    body = batch() | {"events": [events[0] | {"video_id": "dQw4w9WgXcQ"}]}
    assert client.post("/telemetry/events", json=body).status_code == 422


def test_batches_are_bounded_and_ids_must_be_uuids():
    client = TestClient(create_app(StubVision(), telemetry=ListSink()))
    big = batch()
    big["events"] = big["events"] * 101
    assert client.post("/telemetry/events", json=big).status_code == 422
    assert (
        client.post("/telemetry/events", json=batch() | {"install_id": "phone-1"}).status_code
        == 422
    )


def test_collection_off_accepts_and_drops():
    client = TestClient(create_app(StubVision()))
    assert client.post("/telemetry/events", json=batch()).json() == {"accepted": 0}
    assert build_telemetry_sink(Settings.from_env({})) is None
    assert isinstance(
        build_telemetry_sink(Settings.from_env({"TELEMETRY_FILE": "/tmp/x.jsonl"})), JsonlSink
    )


def test_each_request_is_recorded_by_route_template_without_body():
    sink = ListSink()
    client = TestClient(create_app(StubVision(), telemetry=sink))
    client.post("/dishes/videos", json={"dish_id": "nope"})
    client.get("/dishes/no-such-dish/recipe")
    client.get("/health")
    client.post("/telemetry/events", json=batch())
    requests = [r for r in sink.records if r["kind"] == "request"]
    assert [(r["http.route"], r["http.response.status_code"]) for r in requests] == [
        ("/dishes/videos", 422),
        ("/dishes/{dish_id}/recipe", 422),
    ]
    names = {
        "kind",
        "t",
        "http.request.method",
        "http.route",
        "http.response.status_code",
        "duration_ms",
    }
    assert all(set(r) == names for r in requests)
    assert {r["http.request.method"] for r in requests} == {"POST", "GET"}


# --- integrity review (2026-11-20) ------------------------------------------------------------


def test_the_usage_file_stops_at_its_size_limit(tmp_path, caplog):
    path = tmp_path / "usage.jsonl"
    sink = JsonlSink(path, max_bytes=40)
    sink.write([{"n": 1}])
    sink.write([{"n": 2}])
    sink.write([{"n": 3, "pad": "x" * 50}])  # would pass the limit: dropped
    sink.write([{"n": 4, "pad": "x" * 50}])
    assert [json.loads(line)["n"] for line in path.read_text().splitlines()] == [1, 2]
    assert caplog.text.count("size limit") == 1


def test_a_dish_id_outside_the_dish_list_is_not_stored():
    sink = ListSink()
    client = TestClient(create_app(StubVision(), telemetry=sink))
    events = [
        {"name": "dish_open", "t": 1, "dish_id": "kimchi-fried-rice"},
        {"name": "dish_open", "t": 2, "dish_id": "my-secret-text"},
    ]
    body = {"install_id": INSTALL, "session_id": SESSION, "app_version": "1.0", "events": events}
    assert client.post("/telemetry/events", json=body).status_code == 202
    opens = [r for r in sink.records if r.get("kind") == "app"]
    assert [r.get("dish_id") for r in opens] == ["kimchi-fried-rice", None]


def test_a_settings_error_shows_no_part_of_a_key():
    key = "sk-or-v1-abcdefghijklmnopqrstuvwxyz0123456789"
    with pytest.raises(ValueError) as error:
        Settings.from_env({"VISION_PROVIDER": "openrouter", "YOUTUBE_API_KEY": key})
    assert not any(key[i : i + 6] in str(error.value) for i in range(len(key) - 5))


def test_a_blank_dish_key_turns_the_model_off_as_before():
    settings = Settings.from_env({"DISH_LLM_API_KEY": "  ", "OPENROUTER_API_KEY": "or-key"})
    assert settings.dish_model_key == ""
