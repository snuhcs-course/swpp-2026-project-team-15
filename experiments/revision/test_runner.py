"""End-to-end matrix, failure-stop, persistence and CLI tests without network."""
# AI-generated initial importer with Codex (GPT-6.1 Sol)
# 2026-10-14 to 2026-10-17; reviewed by Soohyun An

from contextlib import redirect_stderr, redirect_stdout
import csv
import hashlib
from io import StringIO, BytesIO
import json
import os
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch
from urllib.error import HTTPError

from experiments.revision.cases import Case, RECIPES, matrix
from experiments.revision.mock_llm import MOCK_REFUSAL, MockLLM
from experiments.revision.reports import SCORES, write_json
from experiments.revision.run_experiment import RunSummary, main, run
from experiments.revision.support import (OfflineTestCase, create_database,
                                              feasible, model_raw, temporary_workspace)
from server.recipe_revision import LLMResponse
from server.recipe_revision.adapters import ChatCompletionsLLM


class RunnerTests(OfflineTestCase):
    """Exercise complete and partial runs using source snapshots and fake judgments."""

    def setUp(self):
        super().setUp()
        temporary = temporary_workspace()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.database = self.root / "recipes.sqlite3"
        self.output = self.root / "runs"
        create_database(self.database)
        # CLI tests must never read the developer's real .env or credentials.
        root_patch = patch.multiple("experiments.revision.run_experiment",
                                    REPO_ROOT=self.root, SERVER_ROOT=self.root)
        root_patch.start()
        self.addCleanup(root_patch.stop)

    def read_json(self, path):
        return json.loads(path.read_text(encoding="utf-8"))

    def read_csv(self, path):
        with path.open(encoding="utf-8-sig", newline="") as handle:
            return list(csv.DictReader(handle))

    def script(self):
        return {case.case_id: MOCK_REFUSAL for case in matrix()}

    def test_full_run_keeps_refusals_and_shape_valid_violations(self):
        before = hashlib.sha256(self.database.read_bytes()).hexdigest()
        answers = self.script()
        answers["AI-E0-9"] = model_raw(feasible())
        answers["AI-E0-97"] = model_raw(feasible(999))
        requests = []
        scripted = MockLLM(answers)
        llm = Mock()

        def generate(request):
            requests.append(request)
            return scripted.generate(request)

        llm.generate.side_effect = generate
        summary = run(self.database, self.output, llm, scripted.configuration())
        self.assertTrue(summary.complete)
        self.assertEqual(summary.attempted, 32)
        self.assertEqual(llm.generate.call_count, 32)
        self.assertEqual(before, hashlib.sha256(self.database.read_bytes()).hexdigest())
        meta = self.read_json(summary.directory / "metadata.json")
        self.assertEqual(meta["database_sha256"], before)
        self.assertEqual(meta["run_status"], "completed")
        self.assertEqual(len(meta["planned_cases"]), 32)
        self.assertEqual(meta["unattempted_case_ids"], [])
        self.assertEqual(meta["recorded_case_ids"], [case.case_id for case in matrix()])
        self.assertNotIn("diagnostics", meta)
        observed = self.read_json(summary.directory / "AI-E0-97.json")
        self.assertEqual(observed["status"], "revised")
        self.assertEqual(observed["model_result"]["revised_recipe"]["ingredients"][0]["ingredient_id"], 999)
        self.assertEqual(len(observed["original"]["ingredients"]), 3)
        self.assertEqual(observed["original"]["ingredients"][1]["original_name"], "[양념]계란")
        self.assertEqual(observed["request_metadata"]["messages"][1]["content"], requests[2].user)
        for index, request in enumerate(requests):
            payload = json.loads(request.user)
            self.assertEqual(payload["original"]["recipe_id"], matrix()[index].recipe_id)
            self.assertEqual(len(payload["inventory"]), 7 if index < 16 else 10)
            self.assertEqual(len(request.to_dict()["messages"]), 2)
        results = self.read_csv(summary.directory / "results.csv")
        evaluations = self.read_csv(summary.directory / "evaluation.csv")
        self.assertEqual(len(results), 32)
        self.assertEqual(len(evaluations), 32)
        self.assertEqual(list(results[0]),
                         ["run_id", "case_id", "recipe_name", "status", "reason", "artifact"])
        self.assertEqual(list(evaluations[0]),
                         ["run_id", "case_id", "recipe_name", *SCORES,
                          "reviewer", "rubric_version", "notes"])
        self.assertEqual(set(results[0]) & set(evaluations[0]),
                         {"run_id", "case_id", "recipe_name"})
        self.assertEqual([row["case_id"] for row in results],
                         [row["case_id"] for row in evaluations])
        for result, evaluation, case in zip(results, evaluations, matrix()):
            self.assertEqual(result["recipe_name"], dict(RECIPES)[case.recipe_id])
            self.assertEqual(evaluation["recipe_name"], result["recipe_name"])
            self.assertEqual(result["run_id"], meta["run_id"])
            self.assertEqual(evaluation["run_id"], result["run_id"])
            self.assertEqual([evaluation[key] for key in ("reviewer", "rubric_version", "notes")],
                             [""] * 3)
        self.assertFalse((summary.directory / "cases").exists())
        self.assertEqual(len(list(summary.directory.glob("AI-*.json"))), 32)
        for row in results:
            self.assertEqual(row["artifact"], f"{row['case_id']}.json")
            artifact = summary.directory / row["artifact"]
            self.assertTrue(artifact.is_file())
            self.assertEqual(self.read_json(artifact)["case_id"], row["case_id"])
            for field in ("diagnostics", "checks", "live_compatibility_verified"):
                self.assertNotIn(field, self.read_json(artifact))
        self.assertEqual([evaluations[0][key] for key in SCORES], [""] * 4)
        self.assertEqual([evaluations[1][key] for key in SCORES], ["", "N/A", "N/A", "N/A"])
        self.assertEqual([evaluations[2][key] for key in SCORES], [""] * 4)
        self.assertTrue((summary.directory / "evaluation.csv").read_bytes().startswith(b"\xef\xbb\xbf"))
        self.assertTrue((summary.directory / "results.csv").read_bytes().startswith(b"\xef\xbb\xbf"))

    def test_csv_uses_original_name_and_preserves_json_feasibility(self):
        revised = feasible()
        revised["revised_recipe"]["name"] = "Renamed mock dish"
        revised["reason"] = ""
        llm = MockLLM({"AI-E0-9": model_raw(revised)}, cases=(Case("AI-E0", 9),))
        summary = run(self.database, self.output, llm, llm.configuration(),
                      cases=(Case("AI-E0", 9),))
        record = self.read_json(summary.directory / "AI-E0-9.json")
        self.assertEqual(record["model_result"], revised)
        self.assertTrue(record["model_result"]["can_revise"])
        for filename in ("results.csv", "evaluation.csv"):
            row = self.read_csv(summary.directory / filename)[0]
            self.assertEqual(row["recipe_name"], record["original"]["name"])
            self.assertNotIn("can_revise", row)
        result = self.read_csv(summary.directory / "results.csv")[0]
        self.assertEqual(result["status"], "revised")
        self.assertEqual(result["reason"], "")

    def test_csv_run_case_keys_disambiguate_repeated_runs(self):
        sheets = {"results.csv": [], "evaluation.csv": []}
        for run_id in ("first", "second"):
            cases = (Case("AI-E0", 9),)
            llm = MockLLM(cases=cases)
            summary = run(self.database, self.output, llm, llm.configuration(),
                          cases=cases, run_id=run_id)
            for filename, rows in sheets.items():
                rows.extend(self.read_csv(summary.directory / filename))
        keys = []
        for rows in sheets.values():
            self.assertEqual({row["case_id"] for row in rows}, {"AI-E0-9"})
            keys.append({(row["run_id"], row["case_id"]) for row in rows})
            self.assertEqual(len(keys[-1]), 2)
        self.assertEqual(keys[0], keys[1])

    def test_first_operational_error_stops_after_preserving_existing_results(self):
        for index, failure in enumerate(({"api_error": "simulated timeout"}, "malformed JSON",
                                         model_raw({**feasible(), "revised_recipe": None}))):
            responses = self.script()
            responses["AI-E0-9"] = model_raw(feasible())
            responses["AI-E0-97"] = failure
            llm = MockLLM(responses)
            summary = run(self.database, self.output, llm, llm.configuration(), run_id=f"failure-{index}")
            self.assertFalse(summary.complete)
            self.assertEqual(llm.calls, 3)
            self.assertEqual(summary.attempted, 3)
            meta = self.read_json(summary.directory / "metadata.json")
            self.assertEqual(meta["stopping_case_id"], "AI-E0-97")
            self.assertTrue(meta["stopping_reason"])
            self.assertEqual(len(meta["unattempted_case_ids"]), 29)
            self.assertTrue(meta["finished_at"])
            self.assertEqual(len(list(summary.directory.glob("AI-*.json"))), 3)
            self.assertEqual(self.read_json(summary.directory / "AI-E0-9.json")["status"], "revised")
            error = self.read_json(summary.directory / "AI-E0-97.json")
            self.assertIsNone(error["model_result"])
            if isinstance(failure, str):
                self.assertEqual(error["raw_response"], failure)
            evaluations = self.read_csv(summary.directory / "evaluation.csv")
            self.assertEqual(len(evaluations), 3)
            results = self.read_csv(summary.directory / "results.csv")
            self.assertEqual([row["status"] for row in results],
                             ["revised", "refused", error["status"]])
            self.assertEqual(results[1]["reason"], json.loads(MOCK_REFUSAL)["result"]["reason"])
            self.assertEqual(results[-1]["reason"], error["error"])
            self.assertEqual(results[-1]["recipe_name"], error["original"]["name"])
            self.assertEqual(evaluations[-1]["case_id"], results[-1]["case_id"])
            self.assertFalse((summary.directory / "cases").exists())
            for row in self.read_csv(summary.directory / "results.csv"):
                self.assertEqual(row["artifact"], f"{row['case_id']}.json")
                self.assertTrue((summary.directory / row["artifact"]).is_file())
            self.assertEqual([evaluations[-1][key] for key in SCORES], ["N/A"] * 4)

    def test_error_on_final_case_is_still_incomplete(self):
        responses = self.script()
        responses["AI-E1-421"] = {"api_error": "final failure"}
        llm = MockLLM(responses)
        summary = run(self.database, self.output, llm, llm.configuration())
        meta = self.read_json(summary.directory / "metadata.json")
        self.assertFalse(summary.complete)
        self.assertEqual(summary.attempted, 32)
        self.assertEqual(meta["unattempted_case_ids"], [])
        self.assertEqual(meta["stopping_case_id"], "AI-E1-421")

    def test_new_run_does_not_resume_or_overwrite_review(self):
        responses = self.script()
        responses["AI-E0-18"] = "broken"
        first = MockLLM(responses)
        stopped = run(self.database, self.output, first, first.configuration(), run_id="stopped")
        review = stopped.directory / "evaluation.csv"
        original = review.read_bytes() + b"manual review retained\n"
        review.write_bytes(original)
        retry = MockLLM()
        with self.assertRaises(FileExistsError):
            run(self.database, self.output, retry, retry.configuration(), run_id="stopped")
        self.assertEqual(retry.calls, 0)
        second = run(self.database, self.output, retry, retry.configuration())
        self.assertEqual(retry.calls, 32)
        self.assertNotEqual(stopped.directory, second.directory)
        self.assertEqual(review.read_bytes(), original)
        with redirect_stderr(StringIO()), self.assertRaises(SystemExit) as caught:
            main(["--resume", "stopped"])
        self.assertEqual(caught.exception.code, 2)

    def test_keyboard_interrupt_keeps_saved_cases_and_marks_incomplete(self):
        llm = Mock()
        llm.generate.side_effect = [LLMResponse(MOCK_REFUSAL), KeyboardInterrupt()]
        with self.assertRaises(KeyboardInterrupt):
            run(self.database, self.output, llm, {"provider": "mock"}, run_id="interrupt")
        directory = self.output / "interrupt"
        meta = self.read_json(directory / "metadata.json")
        self.assertFalse(meta["complete"])
        self.assertEqual(meta["run_status"], "interrupted")
        self.assertEqual(meta["recorded_case_ids"], ["AI-E0-9"])
        self.assertEqual(meta["attempted_case_ids"], ["AI-E0-9", "AI-E0-18"])
        self.assertEqual(len(self.read_csv(directory / "evaluation.csv")), 1)
        self.assertEqual(llm.generate.call_count, 2)

    def test_case_persistence_error_stops_future_calls(self):
        llm = MockLLM()

        def write(path, value):
            if path.name == "AI-E0-18.json":
                raise OSError("simulated full disk")
            return write_json(path, value)

        with patch("experiments.revision.run_experiment.write_json", side_effect=write):
            with self.assertRaises(OSError):
                run(self.database, self.output, llm, llm.configuration(), run_id="write-error")
        self.assertEqual(llm.calls, 2)
        directory = self.output / "write-error"
        self.assertTrue((directory / "AI-E0-9.json").exists())
        meta = self.read_json(directory / "metadata.json")
        self.assertFalse(meta["complete"])
        self.assertIn("OSError", meta["stopping_reason"])
        self.assertEqual(meta["diagnostics"]["stage"], "persistence")
        self.assertEqual(meta["recorded_case_ids"], ["AI-E0-9"])

    def test_sheet_persistence_failure_keeps_case_record(self):
        llm = MockLLM()
        from experiments.revision.reports import write_sheets

        def sheets(directory, records):
            if len(records) == 2:
                raise OSError("simulated sheet failure")
            write_sheets(directory, records)

        with patch("experiments.revision.run_experiment.write_sheets", side_effect=sheets), self.assertRaises(OSError):
            run(self.database, self.output, llm, llm.configuration(), run_id="sheet-error")
        self.assertEqual(llm.calls, 2)
        directory = self.output / "sheet-error"
        self.assertTrue((directory / "AI-E0-18.json").exists())
        self.assertEqual(len(self.read_json(directory / "metadata.json")["recorded_case_ids"]), 2)

    def test_cli_is_offline_by_default_and_requires_live_opt_in(self):
        with patch("server.recipe_revision.adapters.ChatCompletionsLLM.from_environment",
                   side_effect=AssertionError("Live configuration forbidden")):
            with redirect_stdout(StringIO()):
                self.assertEqual(main(["--db", str(self.database), "--output-dir", str(self.output)]), 0)
            with redirect_stderr(StringIO()), self.assertRaises(SystemExit) as caught:
                main(["--provider", "chat-completions", "--db", str(self.database)])
            self.assertEqual(caught.exception.code, 2)
        with redirect_stdout(StringIO()), self.assertRaises(SystemExit) as caught:
            main(["--help"])
        self.assertEqual(caught.exception.code, 0)

    def test_cli_mock_file_returns_failure_exit_without_live_calls(self):
        responses = self.script()
        responses["AI-E0-18"] = {"api_error": "fixture failure"}
        fixture = self.root / "responses.json"
        fixture.write_text(json.dumps(responses, ensure_ascii=False), encoding="utf-8")
        with redirect_stdout(StringIO()):
            code = main(["--provider", "mock", "--mock-responses", str(fixture),
                         "--all", "--db", str(self.database), "--output-dir", str(self.output)])
        self.assertEqual(code, 1)
        directory = next(self.output.iterdir())
        self.assertEqual(self.read_json(directory / "metadata.json")["stopping_case_id"], "AI-E0-18")

    def test_bad_mock_fixture_fails_before_calls(self):
        for responses in ({}, {**self.script(), "AI-E0-9": {}}, {**self.script(), "extra": "ignored"}):
            with self.subTest(responses=responses), self.assertRaises(ValueError):
                MockLLM(responses)

    def test_dotenv_uses_server_root_and_preserves_existing_environment(self):
        (self.root / ".env").write_text(
            "REVISION_LLM_ENDPOINT=https://file.example.test/v1/chat/completions\n"
            "REVISION_LLM_MODEL=file-model\nREVISION_LLM_API_KEY=file-fixture-key\n",
            encoding="utf-8")
        other = self.root / "other-working-directory"
        other.mkdir()
        (other / ".env").write_text("REVISION_LLM_MODEL=wrong-directory\n", encoding="utf-8")
        previous_directory = Path.cwd()
        try:
            os.chdir(other)
            with patch.dict(os.environ, {"REVISION_LLM_MODEL": "shell-model",
                                         "REVISION_LLM_API_KEY": ""}, clear=True):
                with patch("experiments.revision.run_experiment.run",
                           return_value=RunSummary(self.output, True, 32, None)) as experiment, redirect_stdout(StringIO()):
                    self.assertEqual(main([]), 0)
                    experiment.call_args.kwargs["make_llm"]()
                self.assertEqual(os.environ["REVISION_LLM_ENDPOINT"],
                                 "https://file.example.test/v1/chat/completions")
                self.assertEqual(os.environ["REVISION_LLM_MODEL"], "shell-model")
                self.assertEqual(os.environ["REVISION_LLM_API_KEY"], "")
        finally:
            os.chdir(previous_directory)

    def test_missing_dotenv_and_api_key_allow_selected_mock_run(self):
        self.assertFalse((self.root / ".env").exists())
        with patch.dict(os.environ, {}, clear=True), redirect_stdout(StringIO()):
            self.assertEqual(main(["--db", str(self.database), "--output-dir", str(self.output)]), 0)
            self.assertNotIn("REVISION_LLM_API_KEY", os.environ)
        directory = next(self.output.iterdir())
        metadata = self.read_json(directory / "metadata.json")
        self.assertTrue(metadata["complete"])
        self.assertEqual(metadata["recorded_case_ids"], ["AI-E0-9"])
        self.assertEqual(metadata["configuration"]["provider"], "mock")

    def test_cli_selects_one_experiment_and_recipe_with_matching_fixture(self):
        for experiment in (0, 1):
            for recipe_id, _ in RECIPES:
                with self.subTest(experiment=experiment, recipe_id=recipe_id):
                    case_id = f"AI-E{experiment}-{recipe_id}"
                    fixture = self.root / "selected.json"
                    fixture.write_text(json.dumps({case_id: MOCK_REFUSAL}), encoding="utf-8")
                    output = self.output / case_id
                    with redirect_stdout(StringIO()) as console:
                        code = main(["--experiment-num", str(experiment), "--recipe-id", str(recipe_id),
                                     "--mock-responses", str(fixture), "--db", str(self.database),
                                     "--output-dir", str(output)])
                    self.assertEqual(code, 0)
                    self.assertIn("1/1 attempts", console.getvalue())
                    directory = next(output.iterdir())
                    meta = self.read_json(directory / "metadata.json")
                    self.assertEqual(meta["recorded_case_ids"], [case_id])
                    self.assertEqual(list(meta["inventories"]), [f"AI-E{experiment}"])
                    record = self.read_json(directory / f"{case_id}.json")
                    self.assertEqual(record["original"]["recipe_id"], recipe_id)
                    self.assertEqual(len(record["inventory"]), 7 if experiment == 0 else 10)

    def test_cli_all_aliases_run_only_selected_inventory(self):
        for experiment, flag in ((0, "--all"), (1, "-all")):
            output = self.output / str(experiment)
            with redirect_stdout(StringIO()) as console:
                code = main(["--experiment-num", str(experiment), flag,
                             "--db", str(self.database), "--output-dir", str(output)])
            self.assertEqual(code, 0)
            self.assertIn("16/16 attempts", console.getvalue())
            metadata = self.read_json(next(output.iterdir()) / "metadata.json")
            self.assertEqual(metadata["recorded_case_ids"],
                             [f"AI-E{experiment}-{recipe_id}" for recipe_id, _ in RECIPES])

    def test_cli_invalid_or_conflicting_selection_never_constructs_model(self):
        for options in (["--experiment-num", "2"], ["--recipe-id", "999"],
                        ["--recipe-id", "9", "--all"]):
            with patch("experiments.revision.run_experiment.MockLLM") as factory:
                with redirect_stderr(StringIO()), self.assertRaises(SystemExit) as caught:
                    main(options)
                self.assertEqual(caught.exception.code, 2)
                factory.assert_not_called()

    def test_selected_run_preflight_ignores_unselected_recipes_and_inventory(self):
        import sqlite3
        from contextlib import closing

        with closing(sqlite3.connect(self.database)) as connection, connection:
            connection.execute("DELETE FROM recipe WHERE recipe_id != 9")
            connection.execute("DELETE FROM ingredient WHERE ingredient_id IN (345,9,147)")
        with redirect_stdout(StringIO()):
            code = main(["--db", str(self.database), "--output-dir", str(self.output)])
        self.assertEqual(code, 0)

    def test_selected_full_fixture_uses_correct_case_and_stops_on_error(self):
        cases = (Case("AI-E1", 421),)
        responses = self.script()
        responses["AI-E1-421"] = {"api_error": "selected failure"}
        llm = MockLLM(responses, cases=cases)
        summary = run(self.database, self.output, llm, llm.configuration(), cases=cases)
        self.assertFalse(summary.complete)
        self.assertEqual(llm.calls, 1)
        metadata = self.read_json(summary.directory / "metadata.json")
        self.assertEqual(metadata["stopping_case_id"], "AI-E1-421")
        self.assertEqual(metadata["unattempted_case_ids"], [])

    def test_dotenv_settings_reach_existing_environment_adapter_without_calls(self):
        (self.root / ".env").write_text(
            "REVISION_LLM_ENDPOINT=https://file.example.test/v1/chat/completions\n"
            "REVISION_LLM_MODEL=file-model\nREVISION_LLM_API_KEY=file-fixture-key\n",
            encoding="utf-8")
        with patch.dict(os.environ, {}, clear=True):
            with patch("experiments.revision.run_experiment.run",
                       return_value=RunSummary(self.output, True, 32, None)) as experiment, redirect_stdout(StringIO()):
                self.assertEqual(main(["--provider", "chat-completions", "--allow-live-api"]), 0)
            adapter = experiment.call_args.kwargs["make_llm"]()
            config = adapter.configuration()
            self.assertEqual(adapter.model, "file-model")
            self.assertEqual(config["endpoint"], "https://file.example.test/v1/chat/completions")
            self.assertEqual(os.environ["REVISION_LLM_API_KEY"], "file-fixture-key")
            self.assertNotIn("file-fixture-key", json.dumps(config))

    def http_adapter(self, response):
        """Return an adapter backed by a fake HTTP response or transport error."""
        transport = MagicMock()
        if isinstance(response, Exception):
            transport.side_effect = response
        else:
            transport.return_value.__enter__.return_value.read.return_value = response
        adapter = ChatCompletionsLLM("https://example.test/chat/completions", "mock-model",
                                     "fixture-key", transport=transport)
        return adapter, transport

    def test_mocked_http_success_preserves_usage_without_diagnostics(self):
        body = json.dumps({"id": "test-request", "choices": [{"finish_reason": "stop",
                           "message": {"content": model_raw(feasible())}}],
                           "usage": {"total_tokens": 15}}).encode()
        adapter, transport = self.http_adapter(body)
        factory = Mock(return_value=adapter)
        summary = run(self.database, self.output, cases=(Case("AI-E0", 9),), make_llm=factory)
        factory.assert_called_once()
        transport.assert_called_once()
        request = json.loads(transport.call_args.args[0].data)
        self.assertTrue(request["response_format"]["json_schema"]["strict"])
        schema = request["response_format"]["json_schema"]
        self.assertEqual(schema["name"], "recipe_revision_v3")
        self.assertEqual(len(schema["schema"]["properties"]["result"]["anyOf"]), 2)
        record = self.read_json(summary.directory / "AI-E0-9.json")
        self.assertTrue(summary.complete)
        self.assertEqual(record["model_result"], feasible())
        self.assertEqual(record["raw_response"], model_raw(feasible()))
        self.assertEqual(record["request_metadata"]["provider_metadata"]["usage"], {"total_tokens": 15})
        for field in ("diagnostics", "checks", "live_compatibility_verified"):
            self.assertNotIn(field, record)

    def test_direct_adapter_only_needs_generation_with_explicit_configuration(self):
        class GenerateOnly:
            """Minimal core adapter without experiment configuration methods."""

            def generate(self, request):
                return LLMResponse(MOCK_REFUSAL)

        config = {"provider": "mock", "model": "generation-only"}
        summary = run(self.database, self.output, GenerateOnly(), config,
                      cases=(Case("AI-E0", 9),))
        self.assertTrue(summary.complete)
        metadata = self.read_json(summary.directory / "metadata.json")
        self.assertEqual(metadata["configuration"], config)

    def test_http_and_parsing_errors_record_distinct_stages_and_never_retry(self):
        answers = (
            (HTTPError("https://example.test", 401, "fixture-key", {}, BytesIO(b"private-provider-body")),
             "api_error", "api_request", None),
            (b'{"choices": [], "private": "private-provider-body"}',
             "response_format_error", "provider_response", None),
            (b'invalid \xff provider data', "response_format_error", "provider_response", None),
            (json.dumps({"choices": [{"finish_reason": "length", "message": {"content": "partial fixture-key"}}]}).encode(),
             "response_format_error", "provider_response", "partial [REDACTED]"),
            (json.dumps({"choices": [{"finish_reason": "stop", "message": {"content": "broken fixture-key"}}]}).encode(),
             "response_format_error", "response_parsing", "broken [REDACTED]"),
            (json.dumps({"choices": [{"finish_reason": "stop", "message": {
                "content": model_raw({**feasible(), "revised_recipe": None})}}]}).encode(),
             "response_format_error", "response_parsing", None),
        )
        for index, (answer, status, stage, raw_text) in enumerate(answers):
            with self.subTest(index=index):
                adapter, transport = self.http_adapter(answer)
                summary = run(self.database, self.output, adapter, adapter.configuration(),
                              run_id=f"diagnostic-{index}",
                              cases=(Case("AI-E0", 9), Case("AI-E0", 18)), secrets=("fixture-key",))
                transport.assert_called_once()
                self.assertFalse(summary.complete)
                record = self.read_json(summary.directory / "AI-E0-9.json")
                self.assertEqual(record["status"], status)
                self.assertEqual(record["diagnostics"], {"stage": stage, "reason": record["error"]})
                if index != 5:
                    self.assertEqual(record["raw_response"], raw_text)
                metadata = self.read_json(summary.directory / "metadata.json")
                self.assertEqual(metadata["unattempted_case_ids"], ["AI-E0-18"])
                self.assertEqual(metadata["stopping_case_id"], "AI-E0-9")
                for path in summary.directory.iterdir():
                    content = path.read_text(encoding="utf-8-sig")
                    self.assertNotIn("fixture-key", content)
                    self.assertNotIn("private-provider-body", content)
                    self.assertNotIn("Authorization", content)

    def test_configuration_errors_save_metadata_without_attempted_case_rows(self):
        for index, error in enumerate((ValueError("configuration fixture-key"),
                                       RuntimeError("Authorization: Bearer unknown-secret"))):
            factory = Mock(side_effect=error)
            with self.assertRaises(type(error)):
                run(self.database, self.output, make_llm=factory, cases=(Case("AI-E0", 9),),
                    run_id=f"configuration-{index}", secrets=("fixture-key",))
            factory.assert_called_once()
            directory = self.output / f"configuration-{index}"
            self.assertEqual({path.name for path in directory.iterdir()}, {"metadata.json"})
            metadata = self.read_json(directory / "metadata.json")
            self.assertEqual(metadata["diagnostics"]["stage"], "configuration")
            self.assertEqual(metadata["attempted_case_ids"], [])
            self.assertEqual(metadata["unattempted_case_ids"], ["AI-E0-9"])
            text = (directory / "metadata.json").read_text(encoding="utf-8")
            for secret in ("fixture-key", "unknown-secret", "Authorization"):
                self.assertNotIn(secret, text)

    def test_cli_preflight_error_is_saved_before_constructing_model(self):
        with patch("experiments.revision.run_experiment.MockLLM") as factory:
            with redirect_stderr(StringIO()), self.assertRaises(SystemExit) as caught:
                main(["--db", str(self.root / "missing.sqlite3"), "--output-dir", str(self.output)])
        self.assertEqual(caught.exception.code, 1)
        factory.assert_not_called()
        directory = next(self.output.iterdir())
        metadata = self.read_json(directory / "metadata.json")
        self.assertEqual(metadata["diagnostics"]["stage"], "preflight")
        self.assertEqual(metadata["attempted_case_ids"], [])

    def test_cli_configuration_errors_do_not_echo_arbitrary_exception_text(self):
        with patch("experiments.revision.run_experiment.MockLLM",
                   side_effect=RuntimeError("Authorization: Bearer unknown-secret")):
            with redirect_stderr(StringIO()) as console, self.assertRaises(SystemExit) as caught:
                main(["--db", str(self.database), "--output-dir", str(self.output)])
        self.assertEqual(caught.exception.code, 1)
        self.assertIn("RuntimeError", console.getvalue())
        self.assertNotIn("unknown-secret", console.getvalue())
        directory = next(self.output.iterdir())
        self.assertEqual(self.read_json(directory / "metadata.json")["diagnostics"]["stage"], "configuration")

    def test_unexpected_revision_error_is_recorded_safely_and_stops(self):
        llm = Mock()
        llm.generate.side_effect = RuntimeError("Authorization: Bearer unknown-secret")
        summary = run(self.database, self.output, llm, {"provider": "mock"})
        self.assertFalse(summary.complete)
        llm.generate.assert_called_once()
        record = self.read_json(summary.directory / "AI-E0-9.json")
        self.assertEqual(record["status"], "revision_error")
        self.assertEqual(record["diagnostics"]["stage"], "revision")
        self.assertIn("RuntimeError", record["error"])
        self.assertEqual([self.read_csv(summary.directory / "evaluation.csv")[0][key]
                          for key in SCORES], ["N/A"] * 4)
        for path in summary.directory.iterdir():
            text = path.read_text(encoding="utf-8-sig")
            self.assertNotIn("unknown-secret", text)
            self.assertNotIn("Authorization", text)

    def test_known_secrets_are_redacted_from_normal_results_too(self):
        value = feasible()
        value["reason"] = "fixture-key"
        llm = Mock()
        llm.generate.return_value = LLMResponse(model_raw(value))
        summary = run(self.database, self.output, llm, {"model": "fixture-key"},
                      cases=(Case("AI-E0", 9),), secrets=("fixture-key",))
        self.assertTrue(summary.complete)
        record = self.read_json(summary.directory / "AI-E0-9.json")
        self.assertNotIn("diagnostics", record)
        self.assertEqual(record["model_result"]["reason"], "[REDACTED]")
        for path in summary.directory.iterdir():
            self.assertNotIn("fixture-key", path.read_text(encoding="utf-8-sig"))

    def test_unwritable_metadata_failure_is_not_reported_as_success(self):
        factory = Mock()
        with patch("experiments.revision.run_experiment.write_json", side_effect=OSError("private disk error")):
            with self.assertRaises(OSError):
                run(self.database, self.output, make_llm=factory, cases=(Case("AI-E0", 9),))
        factory.assert_not_called()
        self.assertEqual(list(next(self.output.iterdir()).iterdir()), [])

    def test_mocked_http_refusal_is_normal_and_continues(self):
        body = json.dumps({"choices": [{"finish_reason": "stop",
                           "message": {"content": MOCK_REFUSAL}}]}).encode()
        adapter, transport = self.http_adapter(body)
        summary = run(self.database, self.output, adapter, adapter.configuration(),
                      cases=(Case("AI-E0", 9), Case("AI-E0", 18)))
        self.assertTrue(summary.complete)
        self.assertEqual(transport.call_count, 2)
        self.assertNotIn("diagnostics", self.read_json(summary.directory / "metadata.json"))
        for case_id in ("AI-E0-9", "AI-E0-18"):
            record = self.read_json(summary.directory / f"{case_id}.json")
            self.assertEqual(record["status"], "refused")
            self.assertNotIn("diagnostics", record)
            self.assertNotIn("checks", record)
            self.assertNotIn("live_compatibility_verified", record)

    def test_cli_persistence_failure_exits_without_secret_or_success_claim(self):
        with patch("experiments.revision.run_experiment.write_json",
                   side_effect=OSError("unknown-secret")):
            with redirect_stderr(StringIO()) as console, redirect_stdout(StringIO()) as output:
                with self.assertRaises(SystemExit) as caught:
                    main(["--db", str(self.database), "--output-dir", str(self.output)])
        self.assertEqual(caught.exception.code, 1)
        self.assertNotIn("unknown-secret", console.getvalue())
        self.assertIn("if available", console.getvalue())
        self.assertNotIn("Completed", output.getvalue())

    def test_environment_file_failure_is_recorded_as_configuration_error(self):
        with patch("experiments.revision.run_experiment.load_dotenv", side_effect=OSError("unknown-secret")):
            with redirect_stderr(StringIO()), self.assertRaises(SystemExit) as caught:
                main(["--db", str(self.database), "--output-dir", str(self.output)])
        self.assertEqual(caught.exception.code, 1)
        directory = next(self.output.iterdir())
        metadata = self.read_json(directory / "metadata.json")
        self.assertEqual(metadata["diagnostics"]["stage"], "configuration")
        self.assertEqual(metadata["attempted_case_ids"], [])
        self.assertNotIn("unknown-secret", (directory / "metadata.json").read_text(encoding="utf-8"))

    def test_file_loaded_credentials_are_redacted_from_cli_results(self):
        (self.root / ".env").write_text("REVISION_LLM_API_KEY=file-fixture-key\n", encoding="utf-8")
        llm = Mock()
        llm.configuration.return_value = {"provider": "mock"}
        llm.generate.return_value = LLMResponse("broken file-fixture-key")
        with patch.dict(os.environ, {}, clear=True), patch("experiments.revision.run_experiment.MockLLM", return_value=llm):
            with redirect_stdout(StringIO()) as console:
                code = main(["--db", str(self.database), "--output-dir", str(self.output)])
        self.assertEqual(code, 1)
        llm.generate.assert_called_once()
        directory = next(self.output.iterdir())
        record = self.read_json(directory / "AI-E0-9.json")
        self.assertEqual(record["raw_response"], "broken [REDACTED]")
        self.assertNotIn("file-fixture-key", console.getvalue())
        for path in directory.iterdir():
            self.assertNotIn("file-fixture-key", path.read_text(encoding="utf-8-sig"))

    def test_invalid_run_id_is_rejected_before_factory_or_output(self):
        factory = Mock()
        for run_id in ("../escape", "nested/run", ".."):
            with self.subTest(run_id=run_id), self.assertRaises(ValueError):
                run(self.database, self.output, make_llm=factory, run_id=run_id)
        factory.assert_not_called()
        self.assertFalse(self.output.exists())
