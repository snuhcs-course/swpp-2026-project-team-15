# AI-generated with Claude Code (Sonnet 5.5), 2026-11-04; reviewed by Jaehyuk Choi.
"""Similarity-based frame selection and the experiment runner's plan, on synthetic data only."""

import json
import math
import random

import pytest
from experiments.capture import frame_selection as fs
from experiments.capture.experiments import frame_similarity as fsim
from experiments.capture.experiments import run_multi_image as run

SECOND = 1_000_000_000


def test_correlation_and_intersection():
    assert fsim.correlation([1, 2, 3], [2, 4, 6]) == pytest.approx(1.0)
    assert fsim.correlation([1, 2, 3], [3, 2, 1]) == pytest.approx(-1.0)
    assert fsim.correlation([5, 5, 5], [1, 2, 3]) == 1.0  # constant vector: nothing to compare
    assert fsim.intersection([0.5, 0.5], [0.5, 0.5]) == pytest.approx(1.0)
    assert fsim.intersection([1.0, 0.0], [0.0, 1.0]) == 0.0
    assert fsim.similarity("edge", [1, 2], [2, 4]) == pytest.approx(1.0)
    assert fsim.similarity("hist", [0.2, 0.8], [0.2, 0.8]) == pytest.approx(1.0)


def test_kendall_tau_b():
    assert fsim.kendall_tau_b([1, 2, 3, 4], [10, 20, 30, 40]) == pytest.approx(1.0)
    assert fsim.kendall_tau_b([1, 2, 3, 4], [4, 3, 2, 1]) == pytest.approx(-1.0)
    assert math.isnan(fsim.kendall_tau_b([1, 1, 1], [1, 2, 3]))


def test_phased_time_bins_phase_zero_is_the_apps_rule_and_other_phases_differ():
    ts = [i * SECOND // 10 for i in range(50)]  # 5 s at 10 frames per second
    rng = random.Random(3)
    sharp = [rng.uniform(5.0, 20.0) for _ in range(50)]
    assert fsim.phased_time_bins(ts, sharp, 10, 0.0) == fs.time_bins(ts, sharp, max(ts) + 1, 10)
    shifted = fsim.phased_time_bins(ts, sharp, 10, 0.5)
    assert min(shifted) >= 3  # frames before the shifted start are ignored
    assert shifted != fsim.phased_time_bins(ts, sharp, 10, 0.0)
    assert fsim.phased_time_bins([], [], 10, 0.0) == []


def vectors():
    # frames 0 and 1 look identical, 2 and 3 differ from them and from each other
    return [[1, 2, 3], [1, 2, 3], [3, 1, 2], [2, 3, 1]]


def test_removal_order_takes_the_most_similar_frame_first_and_the_less_sharp_on_a_tie():
    order = fsim.removal_order([0, 1, 2, 3], [9.0, 5.0, 7.0, 6.0], vectors(), "edge")
    assert order[0] == 1  # frames 0 and 1 are identical; frame 1 is less sharp
    assert sorted(order) == [0, 1, 2, 3]
    assert fsim.removal_order([0, 1], [1.0, 2.0], vectors()[:2], "edge")[0] == 0
    assert fsim.removal_order([7], [1.0] * 8, [[0, 0, 0]] * 8, "edge") == [7]


def test_drop_similar_keeps_at_least_one_frame():
    sharp = [9.0, 5.0, 7.0, 6.0]
    assert fsim.drop_similar([0, 1, 2, 3], sharp, vectors(), "edge", 1) == [0, 2, 3]
    assert len(fsim.drop_similar([0, 1, 2, 3], sharp, vectors(), "edge", 10)) == 1
    assert fsim.drop_similar([0, 1, 2, 3], sharp, vectors(), "edge", 0) == [0, 1, 2, 3]


def test_random_drop_and_uniform_controls():
    frames = list(range(10))
    kept = fsim.random_drop(frames, 4, "clip|0|7")
    assert len(kept) == 6 and kept == sorted(kept) and set(kept) <= set(frames)
    assert kept == fsim.random_drop(frames, 4, "clip|0|7")
    assert fsim.uniform(list(range(100)), 6)[0] == 0 and len(fsim.uniform(list(range(100)), 6)) == 6


def test_average_linkage_groups_nearby_points():
    points = [0.0, 0.1, 5.0, 5.1, 10.0]
    dist = [[abs(a - b) for b in points] for a in points]
    groups = sorted(sorted(g) for g in fsim.average_linkage(dist, 3))
    assert groups == [[0, 1], [2, 3], [4]]
    assert len(fsim.average_linkage(dist, 1)) == 1
    assert len(fsim.average_linkage([[0.0]], 3)) == 1


def view_clip():
    """12 frames 0.2 s apart: view X (0-3), view Y (4-7), view X again after a gap (8-11)."""
    ts = [i * SECOND // 5 for i in range(12)]
    x, y = [1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0]
    feats = [x] * 4 + [y] * 4 + [x] * 4
    sharp = [10.0] * 12
    sharp[2], sharp[5], sharp[10] = 20.0, 30.0, 25.0
    return ts, sharp, feats


def test_cluster_first_splits_a_revisited_view_into_runs():
    ts, sharp, feats = view_clip()
    chosen, info = fsim.cluster_first(list(range(12)), ts, sharp, feats, "edge", 2)
    assert chosen == [2, 5, 10]  # the revisited view counts twice
    assert info["runs"] == 3 and info["dropped_by_cap"] == 0
    assert sorted(c["runs"] for c in info["clusters"]) == [1, 2]


def test_cluster_first_cap_drops_the_least_sharp_runs():
    ts, sharp, feats = view_clip()
    chosen, info = fsim.cluster_first(list(range(12)), ts, sharp, feats, "edge", 2, cap=2)
    assert chosen == [5, 10] and info["dropped_by_cap"] == 1
    assert fsim.cluster_first([], ts, sharp, feats, "edge", 2)[0] == []


def test_cluster_first_ignores_blurred_frames():
    ts, sharp, feats = view_clip()
    sharp[2] = 0.1  # below half the median: gated out, the next sharpest of its run wins
    chosen, _ = fsim.cluster_first(list(range(12)), ts, sharp, feats, "edge", 2)
    assert 2 not in chosen


def synthetic_clip(n=60, seed=1):
    rng = random.Random(seed)
    ts = [i * SECOND // 12 for i in range(n)]
    sharp = [rng.uniform(5, 20) for _ in range(n)]
    feats = {"edge": [[rng.random() for _ in range(8)] for _ in range(n)]}
    feats["hist"] = [[1 / 8] * 8 for _ in range(n)]
    return ts, sharp, feats


@pytest.mark.parametrize(
    ("arm", "count"),
    [
        ({"name": "b", "type": "time_bins"}, 10),
        ({"name": "d", "type": "drop_similar", "measure": "edge", "drop": 4}, 6),
        ({"name": "r", "type": "random_drop", "drop": 4, "seed": 7}, 6),
        ({"name": "u", "type": "uniform", "count": 6}, 6),
        ({"name": "p", "type": "cluster_pool", "pool_bins": 20, "k": 6, "measure": "edge"}, 6),
        ({"name": "c", "type": "cluster_first", "k": 6, "measure": "edge", "cap": 10}, None),
    ],
)
def test_select_frames_arm_types(arm, count):
    ts, sharp, feats = synthetic_clip()
    for replicate in range(3):
        chosen = fsim.select_frames(arm, ts, sharp, feats, replicate, 3, "A01")
        assert chosen == sorted(chosen) and set(chosen) <= set(range(len(ts)))
        if count is not None:
            assert len(chosen) <= count
        else:
            assert 1 <= len(chosen) <= 10
        if arm["type"] == "cluster_first":
            assert all(i % 3 == replicate for i in chosen)  # stride replicates


def test_select_frames_rejects_unknown_arm_type():
    ts, sharp, feats = synthetic_clip()
    with pytest.raises(ValueError, match="unknown arm type"):
        fsim.select_frames({"name": "x", "type": "nope"}, ts, sharp, feats, 0, 3, "A01")


def test_runner_tokens_prompts_and_plan(capsys):
    assert run.expected_tokens(8) == 8 + 258 * 8
    current = run.multi_prompt(8, "current")
    visible = run.multi_prompt(8, "visible-only")
    assert "never guess" not in current and "never guess" in visible
    assert visible.index("never guess") < visible.index("For each item give name_raw")
    ts, sharp, feats = synthetic_clip()
    clips = {"A01": {"ts": ts, "sharp": sharp, "feats": feats}}
    arms = [
        {"name": "base10", "type": "time_bins"},
        {"name": "blank", "type": "blank", "kinds": ["black", "white"], "repeats": 2, "frames": 8},
    ]
    plan = run.build_plan(arms, clips, 3)
    assert sum(p["arm"] == "base10" for p in plan) == 3
    assert sum(p["arm"] == "blank" for p in plan) == 4
    run.print_plan(plan, 0.10, 0.40)
    out = capsys.readouterr().out
    assert "base10" in out and "7 requests" in out and "estimated cost" in out


def test_offline_report_lists_pairs_and_order_agreement(capsys):
    ts, sharp, feats = synthetic_clip()
    feats["gray"] = [list(v) for v in feats["edge"]]
    run.offline_report({"A01": {"ts": ts, "sharp": sharp, "feats": feats}}, ["edge", "gray"])
    out = capsys.readouterr().out
    assert "A01: 60 frames" in out and "removal order agreement edge/gray: tau 1.00" in out


def write_arms(tmp_path):
    path = tmp_path / "arms.json"
    arms = [{"name": "blank", "type": "blank", "kinds": ["black"], "repeats": 3, "frames": 8}]
    path.write_text(json.dumps({"arms": arms}), encoding="utf-8")
    return path


def test_main_dry_run_sends_nothing(tmp_path, capsys, monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    run.main(["--arms", str(write_arms(tmp_path))])
    out = capsys.readouterr().out
    assert "3 requests" in out and "dry run: no request was sent" in out


def test_main_live_needs_a_key_and_respects_the_call_limit(tmp_path, monkeypatch):
    arms = write_arms(tmp_path)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with pytest.raises(SystemExit, match="OPENROUTER_API_KEY"):
        run.main(["--arms", str(arms), "--allow-live-api"])
    with pytest.raises(SystemExit, match="max-calls"):
        run.main(["--arms", str(arms), "--allow-live-api", "--max-calls", "2"])


def test_clip_ids_follow_file_order(tmp_path):
    for name in ("b.mp4", "a.mp4", "note.txt"):
        (tmp_path / name).write_bytes(b"")
    assert list(run.clip_ids(tmp_path, None)) == ["A01", "A02"]
    assert run.clip_ids(tmp_path, {"A05": "b.mp4"})["A05"] == tmp_path / "b.mp4"


def test_frame_features_with_opencv():
    np = pytest.importorskip("numpy")
    pytest.importorskip("cv2")
    frame = np.zeros((72, 128, 3), np.uint8)
    frame[:, 64:] = 255
    feats = fsim.frame_features(frame, ["edge", "gray", "hist"])
    assert len(feats["edge"]) == 64 * 36 and len(feats["gray"]) == 16 * 9
    assert sum(feats["hist"]) == pytest.approx(1.0)
    assert fsim.frame_sharpness(frame) >= 0
