# AI-generated with Claude Code (Sonnet 5.5), 2026-11-03; human review pending.
"""Frame-selection rules on synthetic sweeps; no media, no network."""

from experiments.capture import frame_selection as fs

SECOND = 1_000_000_000


def sweep(n, fps=10):
    return [i * SECOND // fps for i in range(n)]


def test_time_bins_matches_the_app_selector_vector():
    # Same input and expected output as SweepSelectorTest: 50 frames over 5 s, frame 3 + 5k is
    # the sharpest of each 0.5 s bin.
    sharp = [100.0 if i % 5 == 3 else 80.0 for i in range(50)]
    assert fs.time_bins(sweep(50), sharp, 5 * SECOND, 10) == [3 + 5 * i for i in range(10)]


def test_time_bins_drops_blurred_bins_and_falls_back_to_one_frame():
    ts = [i * SECOND // 2 for i in range(10)]
    sharp = [10.0 if i == 4 else 100.0 for i in range(10)]
    assert 4 not in fs.time_bins(ts, sharp, 5 * SECOND, 10)
    assert fs.time_bins([0, SECOND], [100.0, 10.0], 5 * SECOND, 10) == [0]


def test_uniform_and_single():
    assert fs.uniform(5, 8) == [0, 1, 2, 3, 4]
    assert fs.uniform(143, 8)[0] == 0 and fs.uniform(143, 8)[-1] == 142
    assert fs.single([1.0, 9.0, 3.0]) == [1]


def test_dense_takes_one_frame_per_interval():
    assert fs.dense(sweep(30, fps=10)) == [0, 4, 8, 12, 16, 20, 24, 28]


def never_overlapping(a, b):
    return 0.0, True


def unknown_overlap(a, b):
    return 0.0, False


def test_overlap_groups_spread_when_every_score_ties():
    n = 143
    ts = sweep(n, fps=30)
    sharp = [1.0] * n
    plain = fs.overlap_groups(ts, sharp, never_overlapping, k=8, tie_break=False)
    fixed = fs.overlap_groups(ts, sharp, never_overlapping, k=8, tie_break=True)
    assert len(plain) == len(fixed) == 8
    # Without the tie-break the earliest candidates win and the picks stay at the start.
    assert fs.span(plain, n) < 0.1
    assert fs.span(fixed, n) > 0.9


def test_overlap_groups_merge_frames_that_overlap_and_ignore_unreliable_estimates():
    ts = sweep(40, fps=30)
    sharp = [1.0 + (i % 7) for i in range(40)]
    same_view = lambda a, b: (0.9, True)  # noqa: E731
    one_group = fs.overlap_groups(ts, sharp, same_view, k=8)
    # Overlap alone would give one group; the 0.25 s gap rule cuts the 1.3 s clip into five.
    assert len(one_group) == 5
    unknown = fs.overlap_groups(ts, sharp, unknown_overlap, k=8)
    assert len(unknown) == 8


def test_cap_is_clamped():
    assert fs.clamp_k(3) == 8 and fs.clamp_k(40) == 15
