"""Structural contracts and prompts, with no semantic correctness assumptions."""
# AI-generated initial importer with Codex (GPT-6.1 Sol)
# 2026-10-14 to 2026-10-26; reviewed by Soohyun An

from dataclasses import FrozenInstanceError, asdict
import json
import subprocess
import sys
from unittest.mock import Mock

from server.recipe_revision import (APIError, LLMResponse, ResponseFormatError,
                                   build_request, parse_response, revise)
from server.recipe_revision.core import _validate, output_schema
from experiments.revision.mock_llm import MOCK_REFUSAL
from experiments.revision.support import (OfflineTestCase, ROOT, feasible,
                                              inventory, model_raw, raw, sample_recipe)


class CoreTests(OfflineTestCase):
    """Keep originals unchanged and preserve shape-valid mistakes for observation."""

    def test_prompt_preserves_full_input_and_constraints(self):
        recipe = sample_recipe()
        request = build_request(recipe, inventory())
        payload = json.loads(request.user)
        self.assertEqual(payload["original"], json.loads(raw(asdict(recipe))))
        self.assertEqual(len(payload["original"]["ingredients"]), 2)
        self.assertIsNone(payload["original"]["description"])
        self.assertIn("조리 팁", request.user)
        self.assertEqual(len(payload["inventory"]), 7)
        for phrase in ("identity", "ONLY", "No implicit pantry", "food safety", "Allergy checking is excluded",
                       "no target of one serving", "amounts are unknown", "omission/substitution",
                       "normalized", "not definitive", "or claim safety-verified"):
            self.assertIn(phrase, request.system)
        self.assertNotIn("target_servings", payload)
        with self.assertRaises(FrozenInstanceError):
            recipe.name = "changed"

    def test_core_imports_without_io_adapters(self):
        code = "import sys, server.recipe_revision; assert not any(k in sys.modules for k in ('sqlite3','urllib.request','django','experiments.revision.run_experiment'))"
        result = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_valid_feasible_and_refused_shapes(self):
        self.assertEqual(parse_response(model_raw(feasible())), feasible())
        self.assertFalse(parse_response(MOCK_REFUSAL)["can_revise"])

    def test_wire_schema_enforces_exclusive_outcomes(self):
        schema = output_schema()
        self.assertEqual(schema["type"], "object")
        self.assertNotIn("anyOf", schema)
        branches = schema["properties"]["result"]["anyOf"]
        success, refusal = branches
        self.assertEqual(success["properties"]["can_revise"]["enum"], [True])
        self.assertEqual(refusal["properties"]["can_revise"]["enum"], [False])
        for field in ("ingredients", "steps"):
            self.assertEqual(success["properties"]["revised_recipe"]["properties"][field]["minItems"], 1)
        self.assertEqual(refusal["properties"]["changes"]["maxItems"], 0)
        self.assertEqual(refusal["properties"]["revised_recipe"], {"type": "null"})
        for result, expected_index in ((feasible(), 0), (json.loads(MOCK_REFUSAL)["result"], 1)):
            matches = []
            for index, branch in enumerate(branches):
                try:
                    _validate(result, branch)
                    matches.append(index)
                except ResponseFormatError:
                    pass
            self.assertEqual(matches, [expected_index])

    def test_empty_onion_pancake_success_is_rejected_without_repair(self):
        result = feasible()
        result["reason"] = ""
        result["changes"][0]["reason"] = "필수적인 재료인 양파가 없어서 해당 요리를 만들 수 없습니다."
        result["revised_recipe"].update(name="양파전", ingredients=[], steps=[])
        llm = Mock()
        llm.generate.return_value = LLMResponse(model_raw(result))
        outcome = revise(sample_recipe(), inventory(), llm)
        self.assertEqual(outcome.status, "response_format_error")
        self.assertIsNone(outcome.model_result)
        self.assertEqual(outcome.raw_response, model_raw(result))
        llm.generate.assert_called_once()
        prompt = build_request(sample_recipe(), inventory()).system
        self.assertIn("Refusal explanations belong in reason", prompt)
        self.assertIn("verdict, reason, changes and recipe all agree", prompt)

    def test_current_parser_requires_version_three_envelope(self):
        for text in (raw(feasible()), raw({"result": feasible(), "extra": None}),
                     raw({"result": {"result": feasible()}})):
            with self.subTest(text=text), self.assertRaises(ResponseFormatError):
                parse_response(text)

    def test_invalid_json_and_types(self):
        cases = ["not json", '{"reason":"a","reason":"b"}', "null", "[]", "NaN"]
        for key, value in (("can_revise", "false"), ("can_revise", 1),
                           ("reason", None), ("changes", {})):
            result = feasible()
            result[key] = value
            cases.append(model_raw(result))
        result = feasible()
        result["revised_recipe"]["ingredients"][0]["ingredient_id"] = True
        cases.append(model_raw(result))
        result = feasible()
        del result["reason"]
        cases.append(model_raw(result))
        result = feasible()
        result["extra"] = "unexpected"
        cases.append(model_raw(result))
        for text in cases:
            with self.subTest(text=text), self.assertRaises(ResponseFormatError):
                parse_response(text)

    def test_feasible_top_level_reason_can_be_empty_without_repair(self):
        for reason in ("", " \t\n"):
            result = feasible()
            result["reason"] = reason
            llm = Mock()
            llm.generate.return_value = LLMResponse(model_raw(result))
            outcome = revise(sample_recipe(), inventory(), llm)
            self.assertEqual(outcome.status, "revised")
            self.assertEqual(outcome.model_result["reason"], reason)
            self.assertEqual(outcome.raw_response, model_raw(result))
            self.assertIsNone(outcome.error)
            llm.generate.assert_called_once()

    def test_refusal_still_requires_nonempty_reason(self):
        for reason in ("", " \t\n"):
            result = {"can_revise": False, "reason": reason, "changes": [], "revised_recipe": None}
            with self.subTest(reason=reason), self.assertRaisesRegex(ResponseFormatError, "nonempty reason"):
                parse_response(model_raw(result))

    def test_change_reasons_names_and_instructions_still_require_text(self):
        for target in ("change", "name", "instruction"):
            result = feasible()
            result["reason"] = ""
            if target == "change":
                result["changes"][0]["reason"] = ""
            elif target == "name":
                result["revised_recipe"]["name"] = ""
            else:
                result["revised_recipe"]["steps"][0]["instruction"] = ""
            with self.subTest(target=target), self.assertRaises(ResponseFormatError):
                parse_response(model_raw(result))

    def test_conditional_shapes_and_nested_fields(self):
        invalid = []
        for field, value in (("revised_recipe", None),):
            result = feasible()
            result[field] = value
            invalid.append(result)
        for field in ("ingredients", "steps"):
            result = feasible()
            result["revised_recipe"][field] = []
            invalid.append(result)
        result = feasible()
        result["can_revise"] = False
        invalid.append(result)
        result = feasible()
        result["can_revise"], result["revised_recipe"] = False, None
        invalid.append(result)
        result = feasible()
        result["revised_recipe"]["steps"][0]["instruction"] = 1
        invalid.append(result)
        for result in invalid:
            with self.subTest(result=result), self.assertRaises(ResponseFormatError):
                parse_response(model_raw(result))

    def test_observe_violations_without_changing_source(self):
        recipe = sample_recipe()
        before = asdict(recipe)
        llm = Mock()
        wrong = feasible(999)
        wrong["revised_recipe"]["name"] = "다른 요리"
        wrong["revised_recipe"]["steps"][0]["instruction"] = "없는 재료도 넣는다."
        llm.generate.return_value = LLMResponse(model_raw(wrong), {"request_id": "mock"})
        outcome = revise(recipe, inventory(), llm)
        self.assertEqual(outcome.status, "revised")
        self.assertEqual(outcome.model_result, wrong)
        self.assertEqual(outcome.raw_response, model_raw(wrong))
        self.assertEqual(asdict(recipe), before)
        llm.generate.assert_called_once()

    def test_errors_are_not_infeasibility_and_never_retry(self):
        for answer, expected in ((APIError("safe failure"), "api_error"),
                                 (ResponseFormatError("bad envelope", "original body"), "response_format_error"),
                                 (LLMResponse("{broken"), "response_format_error"),
                                 (LLMResponse(MOCK_REFUSAL), "refused")):
            llm = Mock()
            if isinstance(answer, Exception):
                llm.generate.side_effect = answer
            else:
                llm.generate.return_value = answer
            result = revise(sample_recipe(), inventory(), llm)
            self.assertEqual(result.status, expected)
            self.assertEqual(llm.generate.call_count, 1)
            if expected.endswith("error"):
                self.assertIsNone(result.model_result)
                self.assertTrue(result.error)
            if isinstance(answer, ResponseFormatError):
                self.assertEqual(result.raw_response, "original body")
            if isinstance(answer, LLMResponse):
                self.assertEqual(result.raw_response, answer.text)
