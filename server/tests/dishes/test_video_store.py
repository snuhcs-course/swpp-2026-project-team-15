# AI-generated with Claude Code (Sonnet 5.5), 2026-11-19; reviewed by Jaehyuk Choi.
import json
from datetime import UTC, datetime, timedelta

import pytest

from app.dishes.video_store import VideoStore

NOW = datetime(2026, 11, 19, tzinfo=UTC)
ID = "a" * 11


def _file(tmp_path, data):
    path = tmp_path / "videos.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def _data(fetched, ids=(ID,)):
    return {
        "schema": 1,
        "dishes": {"d": {"fetched_at": fetched, "videos": [{"id": i} for i in ids]}},
    }


def test_no_path_is_an_empty_store():
    assert len(VideoStore.load(None)) == 0
    assert VideoStore.load("").fresh_ids("d", NOW) == []


def test_fresh_entry_is_returned_in_stored_order(tmp_path):
    ids = ("b" * 11, ID)
    store = VideoStore.load(_file(tmp_path, _data((NOW - timedelta(days=29)).isoformat(), ids)))
    assert store.fresh_ids("d", NOW) == list(ids)
    assert store.fresh_ids("other", NOW) == []


def test_entry_of_thirty_days_or_more_is_ignored(tmp_path):
    store = VideoStore.load(_file(tmp_path, _data((NOW - timedelta(days=30)).isoformat())))
    assert store.fresh_ids("d", NOW) == []


def test_time_without_zone_is_read_as_utc(tmp_path):
    store = VideoStore.load(_file(tmp_path, _data("2026-11-18T12:00:00")))
    assert store.fresh_ids("d", NOW) == [ID]


@pytest.mark.parametrize(
    "data",
    [
        {"schema": 2, "dishes": {}},
        {"schema": 1},
        {"schema": 1, "dishes": {"d": {"videos": []}}},
        {"schema": 1, "dishes": {"d": {"fetched_at": "not a time", "videos": []}}},
        _data("2026-11-18T12:00:00+00:00", ("short",)),
    ],
)
def test_invalid_file_stops_the_server_at_startup(tmp_path, data):
    with pytest.raises(ValueError):
        VideoStore.load(_file(tmp_path, data))


def test_unreadable_file_is_an_error(tmp_path):
    with pytest.raises(OSError):
        VideoStore.load(tmp_path / "missing.json")
