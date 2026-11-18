# AI-generated with Claude Code (Opus 5.5), 2026-11-19; reviewed by Jaehyuk Choi.
import json

from experiments.dish_recipes import supplement_videos as sv


def test_new_ids_skips_seen_and_duplicates_in_order():
    assert sv.new_ids(["a", "b", "a", "c"], {"b"}) == ["a", "c"]


def test_rejected_collects_every_judged_video_of_the_dish():
    report = {"d|x": {"dish": "d", "video": "x"}, "e|y": {"dish": "e", "video": "y"}}
    assert sv.rejected(report, "d") == {"x"}


def test_merged_replaces_only_the_given_dishes():
    verified = {"schema": 1, "dishes": {"a": {"fetched_at": "t0", "videos": [{"id": "1"}]}}}
    out = sv.merged(verified, {"b": [{"id": "2"}]}, "t1")
    assert out["dishes"]["a"] == {"fetched_at": "t0", "videos": [{"id": "1"}]}
    assert out["dishes"]["b"] == {"fetched_at": "t1", "videos": [{"id": "2"}]}
    assert out["schema"] == 1


def test_write_atomic_leaves_no_temporary_file(tmp_path):
    target = tmp_path / "out.json"
    sv.write_atomic(target, {"k": "값"})
    assert json.loads(target.read_text("utf-8")) == {"k": "값"}
    assert [p.name for p in tmp_path.iterdir()] == ["out.json"]
