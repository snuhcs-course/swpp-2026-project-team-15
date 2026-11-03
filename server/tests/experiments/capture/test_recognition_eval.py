# AI-generated with Claude Code (Sonnet 5.5), 2026-11-03; reviewed by Jaehyuk Choi.
"""Known-answer tests for the recognition evaluation scorer and the offline planner (no network)."""

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from experiments.capture.recognition import predict, score

DIR = Path(score.HERE)
EGG = {"id": "egg", "names": ["달걀", "계란"], "status": "visible"}
MILK = {"id": "milk", "names": ["우유"], "status": "visible"}
CHEESE = {"id": "cheese", "names": ["치즈"], "status": "ambiguous"}


class MatchingTests(unittest.TestCase):
    def test_substring_either_way_and_normalization(self):
        self.assertTrue(score.name_matches("신선한 달걀 10구", ["달걀"]))
        self.assertTrue(score.name_matches("달걀", ["달걀 10구"]))
        self.assertTrue(score.name_matches(" 계 란 ", ["계란"]))
        self.assertFalse(score.name_matches("우유", ["달걀"]))

    def test_one_character_allowed_name_never_matches(self):
        self.assertFalse(score.name_matches("쌀국수", ["쌀"]))
        self.assertFalse(score.name_matches("쌀", ["쌀"]))
        self.assertTrue(score.name_matches("쌀 백미", ["쌀 백미"]))

    def test_alias_rewrites_a_short_candidate_before_matching(self):
        rows = score.merge([["쌀"]], "M1", {"쌀": "쌀 백미"})
        self.assertEqual(rows, ["쌀 백미"])
        m = score.match_fridge([{"id": "rice", "names": ["쌀 백미"]}], rows)
        self.assertEqual(m["found"], ["rice"])

    def test_one_to_one_and_extras(self):
        m = score.match_fridge([EGG, MILK], ["달걀", "계란", "빵"])
        self.assertEqual(m["found"], ["egg"])
        self.assertEqual(m["missed"], ["milk"])
        self.assertEqual(m["extra"], ["계란", "빵"])

    def test_ambiguous_policy(self):
        excl = score.match_fridge([EGG, CHEESE], ["달걀", "치즈"], "exclude")
        self.assertEqual((excl["extra"], excl["ignored"]), ([], ["치즈"]))
        self.assertEqual(score.metrics(excl)["n_true"], 1)
        incl = score.match_fridge([EGG, CHEESE], ["달걀"], "count_as_item")
        self.assertEqual(incl["missed"], ["cheese"])
        with self.assertRaises(ValueError):
            score.match_fridge([EGG], [], "other")

    def test_metrics(self):
        m = score.metrics(
            {"found": ["a", "b"], "missed": ["c", "d"], "extra": ["x"], "ignored": []}
        )
        self.assertEqual((m["recall"], m["fix_count"]), (0.5, 3))
        self.assertAlmostEqual(m["false_recognition"], 1 / 3)
        empty = score.metrics({"found": [], "missed": [], "extra": [], "ignored": []})
        self.assertIsNone(empty["recall"])


class MergeTests(unittest.TestCase):
    FRAMES = [["우유", "달걀"], ["달걀", "빵"], ["달걀"]]

    def test_strategies(self):
        self.assertEqual(score.merge(self.FRAMES, "M1"), ["우유", "달걀", "빵"])
        self.assertEqual(score.merge(self.FRAMES, "M2"), ["달걀"])
        with self.assertRaises(ValueError):
            score.merge(self.FRAMES, "M9")

    def test_repeated_name_in_one_frame_counts_once(self):
        self.assertEqual(score.merge([["달걀", "달걀"]], "M2"), [])

    def test_first_seen_order_is_stable(self):
        names = [f"재료{i}" for i in range(30)]
        self.assertEqual(score.merge([names, names[::-1]], "M1"), names)


class StatisticsTests(unittest.TestCase):
    def rows(self, gains):
        runs = []
        for i, gain in enumerate(gains):
            fridge = f"F{i}"
            runs.append({"fridge": fridge, "variant": "single", "frames": [["달걀"]]})
            runs.append(
                {"fridge": fridge, "variant": "overlap", "frames": [["달걀", "우유"][: 1 + gain]]}
            )
        key = {"fridges": {f"F{i}": [EGG, MILK] for i in range(len(gains))}}
        return score.score_runs(key, runs), key, runs

    def test_paired_difference_and_interval(self):
        rows, _, _ = self.rows([1] * 6)
        d = score.paired_difference(rows, "overlap", "single", "recall", seed=1)
        self.assertEqual((d["n_units"], d["wins"], d["losses"]), (6, 6, 0))
        self.assertAlmostEqual(d["mean"], 0.5)
        self.assertEqual(d["ci95"], [0.5, 0.5])

    def test_scene_resampling_uses_scenes_as_units(self):
        rows, _, _ = self.rows([1, 1, 1, 0])
        d = score.paired_difference(
            rows, "overlap", "single", "recall", seed=1, scenes=[["F0", "F1", "F2"], ["F3"]]
        )
        self.assertEqual(d["n_units"], 2)
        self.assertAlmostEqual(d["mean"], 0.25)

    def test_single_unit_has_no_interval(self):
        rows, _, _ = self.rows([1])
        self.assertIsNone(score.paired_difference(rows, "overlap", "single", "recall", seed=1)["ci95"])

    def test_evaluate_is_deterministic_and_judges(self):
        _, key, runs = self.rows([1, 0, 1])
        th = json.loads((DIR / "thresholds.json").read_text(encoding="utf-8"))
        first = score.evaluate(key, runs, th, seed=7)
        self.assertEqual(first, score.evaluate(key, runs, th, seed=7))
        self.assertAlmostEqual(first["variants"]["overlap"]["recall"], 5 / 6)
        self.assertTrue(first["verdict"]["overlap"]["recall"]["pass"])
        self.assertFalse(first["verdict"]["single"]["recall"]["pass"])


class ThresholdTests(unittest.TestCase):
    def test_shipped_thresholds_are_frozen_and_complete(self):
        th = json.loads((DIR / "thresholds.json").read_text(encoding="utf-8"))
        self.assertTrue(score.thresholds_frozen(th))
        self.assertEqual(
            set(th["metrics"]),
            {"recall", "false_recognition", "fix_count_mean", "schema_valid_rate"},
        )

    def test_unfrozen_thresholds_report_no_verdict(self):
        th = {"status": "DRAFT", "metrics": {"recall": {"op": ">=", "value": None}}}
        self.assertIn("not frozen", score.judge(th, {"recall": 1.0})["status"])

    def test_judge_applies_operator(self):
        th = {
            "status": "FROZEN",
            "metrics": {
                "recall": {"op": ">=", "value": 0.6},
                "false_recognition": {"op": "<=", "value": 0.3},
            },
        }
        v = score.judge(th, {"recall": 0.7, "false_recognition": 0.5})
        self.assertTrue(v["recall"]["pass"])
        self.assertFalse(v["false_recognition"]["pass"])


class AnswerKeyTests(unittest.TestCase):
    def setUp(self):
        self.key = json.loads((DIR / "answer_key.json").read_text(encoding="utf-8"))

    def test_every_item_is_scoreable(self):
        for fridge, items in self.key["fridges"].items():
            ids = [i["id"] for i in items]
            self.assertEqual(len(ids), len(set(ids)), fridge)
            for item in items:
                self.assertIn(item["status"], ("visible", "ambiguous"))
                self.assertTrue(
                    any(len(score.norm(n)) >= 2 for n in item["names"]), (fridge, item["id"])
                )

    def test_scenes_cover_the_clips_once(self):
        grouped = [f for scene in self.key["scenes"] for f in scene]
        self.assertEqual(len(grouped), len(set(grouped)))
        self.assertTrue(set(grouped) <= set(self.key["fridges"]))

    def test_key_contains_names_only(self):
        text = (DIR / "answer_key.json").read_text(encoding="utf-8")
        for forbidden in (".jpg", ".mp4", "sha256", "/home/", "desc"):
            self.assertNotIn(forbidden, text)

    def test_aliases_map_to_longer_names(self):
        for short, long_ in json.loads((DIR / "aliases.json").read_text(encoding="utf-8")).items():
            self.assertLess(len(short), len(long_))


class PlannerTests(unittest.TestCase):
    SEL = {
        "fridges": {"A01": {"single": ["a.jpg"], "uniform": ["a.jpg", "b.jpg"], "overlap": ["b.jpg", "c.jpg"]}}
    }

    def test_plan_dedupes_shared_frames(self):
        plan = predict.build_plan(self.SEL, repeats=2, mode="per_frame")
        self.assertEqual(len(plan), 2 * 3)
        multi = predict.build_plan(self.SEL, repeats=1, mode="multi_image")
        self.assertEqual([len(s["paths"]) for s in multi], [1, 2, 2])

    def test_expected_input_tokens_follow_the_measured_rule(self):
        self.assertEqual(predict.expected_input_tokens(1), 266)
        self.assertEqual(predict.expected_input_tokens(8), 2072)

    def test_dry_run_sends_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            sel = Path(tmp) / "sel.json"
            sel.write_text(json.dumps(self.SEL), encoding="utf-8")
            out = Path(tmp) / "out.json"
            buf = io.StringIO()
            with redirect_stdout(buf):
                predict.main([str(sel), str(out), "--frames-dir", tmp])
            self.assertIn("dry run", buf.getvalue())
            self.assertFalse(out.exists())

    def test_live_path_with_a_fake_transport(self):
        calls = []

        def fake(payload):
            calls.append(payload)
            reply = {"items": [{"name_raw": "x", "category": "달걀", "confidence": 0.9}]}
            return {
                "choices": [{"finish_reason": "stop", "message": {"content": json.dumps(reply)}}],
                "usage": {"prompt_tokens": 300},
            }

        with tempfile.TemporaryDirectory() as tmp:
            for name in "abc":
                (Path(tmp) / f"{name}.jpg").write_bytes(b"jpeg-" + name.encode())
            plan = predict.build_plan(self.SEL, 1, "per_frame")
            answers = predict.run_plan(plan, Path(tmp), fake, "prompt")
        self.assertEqual(len(calls), 3)
        self.assertEqual(calls[0]["temperature"], 0)
        self.assertEqual(len(calls[0]["messages"][0]["content"]), 2)
        runs = predict.per_frame_runs(self.SEL, answers)
        self.assertEqual(
            {(r["variant"], r["frames_sent"]) for r in runs}, {("single", 1), ("uniform", 2), ("overlap", 2)}
        )
        self.assertTrue(all(r["schema_valid"] for r in runs))

    def test_invalid_reply_is_flagged(self):
        self.assertEqual(predict.parse_response({"choices": []}), ([], False))
        cut = {"choices": [{"finish_reason": "length", "message": {"content": '{"items": []}'}}]}
        self.assertEqual(predict.parse_response(cut), ([], False))


if __name__ == "__main__":
    unittest.main()
