# AI-generated with Claude Code (Sonnet 5.5), 2026-11-18; reviewed by Jaehyuk Choi.
import json
from types import SimpleNamespace

import pytest

from experiments.dish_recipes import captions, collect_videos, coverage, validate_recipe

VIDEO = "abcdefghijk"


def test_parse_duration():
    assert collect_videos.parse_duration("PT1H2M3S") == 3723
    assert collect_videos.parse_duration("PT45S") == 45
    assert collect_videos.parse_duration("P0D") == 0
    assert collect_videos.parse_duration("") == 0


def test_pick_track_takes_korean_manual_then_korean_auto_and_nothing_else():
    assert captions.pick_track([("en", False), ("ko", True), ("ko", False)]) == ("ko", False)
    assert captions.pick_track([("en", False), ("ko", True)]) == ("ko", True)
    assert captions.pick_track([("ja", True), ("en", False)]) is None
    assert captions.pick_track([]) is None


class Blocking(Exception):
    pass


class Plain(Exception):
    pass


ERRORS = SimpleNamespace(
    RequestBlocked=Blocking,
    IpBlocked=Blocking,
    TranscriptsDisabled=KeyError,
    NoTranscriptFound=KeyError,
    VideoUnavailable=KeyError,
    CouldNotRetrieveTranscript=Plain,
)


class FakeApi:
    def __init__(self, tracks, snippets=None, error=None):
        self.tracks, self.snippets, self.error = tracks, snippets or [], error

    def list(self, video_id):
        if self.error:
            raise self.error
        return [SimpleNamespace(language_code=c, is_generated=g) for c, g in self.tracks]

    def fetch(self, video_id, languages):
        return SimpleNamespace(
            language_code=languages[0],
            is_generated=dict(self.tracks)[languages[0]],
            snippets=[SimpleNamespace(start=s, text=t) for s, t in self.snippets],
        )


def test_fetch_transcript_cleans_and_labels():
    api = FakeApi([("ko", True)], [(0.0, "김치를\n썰어요"), (2.04, "  "), (3.0, "볶아요")])
    got = captions.fetch_transcript(VIDEO, api, ERRORS)
    assert got.kind == "auto" and got.language == "ko"
    assert got.snippets == [
        {"start": 0.0, "text": "김치를 썰어요"},
        {"start": 3.0, "text": "볶아요"},
    ]
    assert got.chars == 10


def test_fetch_transcript_none_without_tracks_or_with_disabled_captions():
    assert captions.fetch_transcript(VIDEO, FakeApi([]), ERRORS) is None
    assert captions.fetch_transcript(VIDEO, FakeApi([], error=KeyError()), ERRORS) is None
    assert captions.fetch_transcript(VIDEO, FakeApi([], error=Plain("odd")), ERRORS) is None


def test_fetch_transcript_stops_on_blocking():
    with pytest.raises(captions.Blocked):
        captions.fetch_transcript(VIDEO, FakeApi([], error=Blocking()), ERRORS)
    with pytest.raises(captions.Blocked):
        captions.fetch_transcript(VIDEO, FakeApi([], error=Plain("HTTP 429 Too Many")), ERRORS)


RECORD = {
    "video": {"id": VIDEO},
    "transcript": [
        {"start": 0, "text": "달걀 두 개와 김치를 준비합니다"},
        {"start": 5, "text": "밥을 볶아요"},
    ],
}


def recipe(**changes):
    base = {
        "dish_id": "kimchi-fried-rice",
        "video": {"id": VIDEO, "title": "t", "channel": "c"},
        "source": "ai_structured_from_captions",
        "generated_at": "2026-11-18T00:00:00+00:00",
        "servings": 1,
        "ingredients": [
            {"name": "계란", "amount": "2개", "role": "main"},
            {"name": "김치", "amount": None, "role": "main"},
        ],
        "steps": [{"n": 1, "text": "김치를 썹니다."}, {"n": 2, "text": "밥과 함께 볶습니다."}],
        "tips": [],
        "uncertain": [],
        "caption_gaps": False,
    }
    base.update(changes)
    return base


def test_valid_recipe_accepts_a_synonym_of_a_spoken_ingredient():
    assert validate_recipe.check_recipe(recipe(), RECORD) == []


def test_ingredient_not_in_captions_needs_uncertain():
    rows = [*recipe()["ingredients"], {"name": "참기름", "amount": None, "role": "seasoning"}]
    assert any(
        "참기름" in p for p in validate_recipe.check_recipe(recipe(ingredients=rows), RECORD)
    )
    assert (
        validate_recipe.check_recipe(recipe(ingredients=rows, uncertain=["참기름"]), RECORD) == []
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"steps": [{"n": 1, "text": "김치를 썹니다."}, {"n": 3, "text": "볶습니다."}]},
        {"steps": [{"n": 1, "text": "김치"}, {"n": 2, "text": "가" * 301}]},
        {"steps": [{"n": 1, "text": "Cut the kimchi."}, {"n": 2, "text": "Fry it with rice."}]},
        {"ingredients": [{"name": "김치", "amount": None, "role": "main"}]},
        {"source": "other"},
        {"extra": 1},
    ],
)
def test_invalid_recipes_are_reported(changes):
    assert validate_recipe.check_recipe(recipe(**changes), RECORD)


def test_validator_cli_reports_missing_captions(tmp_path, capsys, monkeypatch):
    path = tmp_path / "r.json"
    path.write_text(json.dumps(recipe(dish_id="no-such-dish")), encoding="utf-8")
    assert validate_recipe.main([str(path)]) == 1
    assert "captions not found" in capsys.readouterr().err
    record = tmp_path / "in.json"
    record.write_text(json.dumps(RECORD), encoding="utf-8")
    assert validate_recipe.main([str(path), "--input", str(record)]) == 0


def test_coverage_report_counts():
    snapshot = {
        "a": {"videos": [{"id": "x"}, {"id": "y"}]},
        "b": {"videos": [{"id": "z"}]},
        "c": {"videos": []},
    }
    inputs = {
        "a": {"video": {"id": "y", "caption_kind": "auto", "language": "ko"}, "caption_chars": 100}
    }
    report = coverage.build_report(["a", "b", "c", "d"], snapshot, inputs, {"b": {"tried": ["z"]}})
    assert report["with_video"] == 2 and report["with_captions"] == 1
    assert report["no_captions"] == ["b"] and report["not_tried"] == []
    assert report["video_rank_used"] == {"2": 1}
    assert report["caption_chars"]["median"] == 100
