# AI-assisted with Codex, 2026-11-11; reviewed by Soohyun An
# Additional output-preview tests assisted by Codex, 2026-11-11; human review pending.
"""Stage 1 acceptance tests derived from the approved quotas and offline boundary.

The CLI JSON interface is specified in the adjacent test README. Missing implementation
must fail these tests rather than be hidden behind skip/xfail or replacement logic.
"""

import importlib
import json
import re
import shlex
import sys
import tomllib
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

pytest_plugins = ("pytester",)

TOOLS_ROOT = Path(__file__).resolve().parents[3]
EXPECTED_CATEGORIES = (
    ("밑반찬", "63", 100),
    ("메인반찬", "56", 90),
    ("국/탕", "54", 60),
    ("찌개", "55", 30),
    ("면/만두", "53", 60),
    ("밥/죽/떡", "52", 100),
    ("퓨전", "61", 20),
    ("양식", "65", 20),
    ("샐러드", "64", 20),
)


def _plan(run_tool, output):
    """Read the real plan command's JSON; do not manufacture expected output."""
    result = run_tool("plan", "--output-dir", str(output))
    assert result.returncode == 0, result.stdout + result.stderr
    assert "FORBIDDEN_IO" not in result.stderr
    return json.loads(result.stdout)


def test_offline_guard_detects_even_caught_network_attempts(run_tool):
    """Verify the test harness fails closed before DNS/network access can occur."""
    result = run_tool(mode="probe")
    assert result.returncode == 97
    assert "FORBIDDEN_IO" in result.stderr


def test_cli_import_is_offline_and_has_no_output(run_tool):
    result = run_tool(mode="import")
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout == ""
    assert "FORBIDDEN_IO" not in result.stderr


@pytest.mark.parametrize("arguments", [(), ("--help",), ("plan", "--help")])
def test_cli_help_is_available_without_network_or_server(run_tool, arguments):
    result = run_tool(*arguments)
    # Typer's no-argument help may use exit code 2; it must still show help.
    assert result.returncode in ({0, 2} if not arguments else {0}), result.stderr
    assert "Usage" in result.stdout + result.stderr
    assert "plan" in result.stdout + result.stderr
    assert "FORBIDDEN_IO" not in result.stderr


def test_plan_preserves_approved_category_order_and_total(run_tool, tmp_path):
    plan = _plan(run_tool, tmp_path / "collection")
    assert [
        (category["name"], str(category["cat4"]), category["quota"])
        for category in plan["categories"]
    ] == list(EXPECTED_CATEGORIES)
    assert plan["total"] == sum(category["quota"] for category in plan["categories"]) == 500
    assert all(type(category["quota"]) is int for category in plan["categories"])


def test_plan_urls_keep_both_filters_and_recommendation_order(run_tool, tmp_path):
    plan = _plan(run_tool, tmp_path / "collection")
    for category, (_, code, _) in zip(plan["categories"], EXPECTED_CATEGORIES, strict=True):
        url = urlsplit(category["list_url"])
        assert (url.scheme, url.netloc, url.path) == (
            "https",
            "www.10000recipe.com",
            "/recipe/list.html",
        )
        assert parse_qs(url.query) == {
            "cat2": ["18"],
            "cat4": [code],
            "order": ["reco"],
            "page": ["1"],
        }


def test_explicit_output_does_not_overwrite_existing_data(run_tool, tmp_path):
    existing = tmp_path / "Recipe.csv"
    existing.write_bytes(b"recipe_id,name\n537,existing\n")
    output = tmp_path / "new-run"
    plan = _plan(run_tool, output)
    assert Path(plan["output_dir"]).resolve() == output.resolve()
    assert existing.read_bytes() == b"recipe_id,name\n537,existing\n"


def test_existing_file_cannot_be_used_as_output_directory(run_tool, tmp_path):
    output = tmp_path / "existing.csv"
    output.write_bytes(b"preserve this file")
    result = run_tool("plan", "--output-dir", str(output))
    assert result.returncode != 0
    assert "output" in (result.stdout + result.stderr).lower()
    assert "FORBIDDEN_IO" not in result.stderr
    assert output.read_bytes() == b"preserve this file"


@pytest.mark.parametrize("protected", ["server", "android", "data/recipes"])
def test_production_paths_are_rejected_as_output(run_tool, protected):
    output = TOOLS_ROOT.parent / protected
    result = run_tool("plan", "--output-dir", str(output))
    assert result.returncode != 0
    assert "output" in (result.stdout + result.stderr).lower()
    assert "FORBIDDEN_IO" not in result.stderr, "Reject paths before opening production files"


def test_config_plans_are_independent(tmp_path, monkeypatch):
    """Building another plan must not change an existing plan or the defaults.

    Immutable category values can be shared safely; object identity is not part
    of this contract. Different output choices must remain local to each plan.
    """
    monkeypatch.syspath_prepend(str(TOOLS_ROOT))
    config = importlib.import_module("crawlers.tenkrecipes.config")
    first_output = tmp_path / "first"
    second_output = tmp_path / "second"
    first = config.build_plan(output_dir=first_output)
    first_categories = [dict(category) for category in first["categories"]]
    first_total = first["total"]

    second = config.build_plan(output_dir=second_output)

    assert Path(first["output_dir"]).resolve() == first_output.resolve()
    assert Path(second["output_dir"]).resolve() == second_output.resolve()
    assert first["total"] == first_total == second["total"] == 500
    assert [dict(category) for category in first["categories"]] == first_categories
    assert [dict(category) for category in second["categories"]] == first_categories

    rebuilt = config.build_plan(output_dir=first_output)
    assert Path(rebuilt["output_dir"]).resolve() == first_output.resolve()
    assert [dict(category) for category in rebuilt["categories"]] == first_categories
    assert Path(second["output_dir"]).resolve() == second_output.resolve()


def test_config_plan_is_deeply_immutable(tmp_path, monkeypatch):
    """Reject changes to the built run plan, independently of other plan instances."""
    monkeypatch.syspath_prepend(str(TOOLS_ROOT))
    config = importlib.import_module("crawlers.tenkrecipes.config")
    plan = config.build_plan(output_dir=tmp_path / "collection")
    with pytest.raises(TypeError):
        plan["total"] = 1
    with pytest.raises(TypeError):
        plan["categories"][0]["quota"] = 1
    assert plan["total"] == 500
    assert plan["categories"][0]["quota"] == 100


def test_default_plan_uses_unique_ignored_run_paths_without_creating_them(monkeypatch):
    """Default previews must stay separate from existing recipes and from each other."""
    monkeypatch.syspath_prepend(str(TOOLS_ROOT))
    config = importlib.import_module("crawlers.tenkrecipes.config")
    first = Path(config.build_plan()["output_dir"])
    second = Path(config.build_plan()["output_dir"])
    expected_parent = TOOLS_ROOT.parent / "data/tenkrecipes/runs"
    assert first.parent == second.parent == expected_parent
    assert first != second
    assert not first.exists()
    assert not second.exists()


def test_cli_plan_is_a_preview_and_resolves_relative_output(run_tool, tmp_path):
    """A preview must not allocate its proposed directory or persist run metadata."""
    plan = _plan(run_tool, Path("relative-run"))
    expected = tmp_path / "workspace/relative-run"
    assert Path(plan["output_dir"]) == expected.resolve()
    assert not expected.exists()
    assert list((tmp_path / "workspace").iterdir()) == []


@pytest.mark.parametrize("relative", [".", "server/nested-run", "tools/crawlers/pixabay/output"])
def test_output_boundaries_cover_ancestors_and_descendants(run_tool, relative):
    output = TOOLS_ROOT.parent / relative
    result = run_tool("plan", "--output-dir", str(output))
    assert result.returncode != 0
    assert "output" in (result.stdout + result.stderr).lower()
    assert "FORBIDDEN_IO" not in result.stderr


def test_output_directory_cannot_have_a_file_as_parent(run_tool, tmp_path):
    parent = tmp_path / "Recipe.csv"
    parent.write_bytes(b"existing recipe data")
    result = run_tool("plan", "--output-dir", str(parent / "run"))
    assert result.returncode != 0
    assert "output" in (result.stdout + result.stderr).lower()
    assert parent.read_bytes() == b"existing recipe data"


def test_html_parser_dependency_stays_in_tools():
    """Check the declared environment boundary without installing or using the network."""
    tools = tomllib.loads((TOOLS_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    server = tomllib.loads(
        (TOOLS_ROOT.parent / "server/pyproject.toml").read_text(encoding="utf-8")
    )
    assert any(dep.lower().startswith("beautifulsoup4") for dep in tools["project"]["dependencies"])
    assert not any(
        dep.lower().startswith("beautifulsoup4") for dep in server["project"]["dependencies"]
    )


def test_default_discovery_includes_both_crawlers(pytester):
    """Exercise actual pytest discovery without importing either crawler implementation."""
    config = (TOOLS_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    pytester.makefile(".toml", pyproject=config)
    for crawler in ("pixabay", "tenkrecipes"):
        tests = pytester.path / "crawlers" / crawler / "tests"
        tests.mkdir(parents=True)
        (tests / f"test_{crawler}_discovery_probe.py").write_text(
            "def test_discovery_probe():\n    pass\n", encoding="utf-8"
        )
    result = pytester.runpytest_subprocess("--collect-only", "-q")
    result.assert_outcomes()
    assert result.ret == 0
    result.stdout.fnmatch_lines(
        ["*pixabay*test_discovery_probe*", "*tenkrecipes*test_discovery_probe*"]
    )


def test_existing_pixabay_modules_are_not_shadowed(monkeypatch):
    """Namespace imports must not replace the existing crawler's bare modules."""
    monkeypatch.syspath_prepend(str(TOOLS_ROOT))
    monkeypatch.syspath_prepend(str(TOOLS_ROOT / "crawlers/pixabay/src"))
    legacy = importlib.import_module("models")
    importlib.import_module("crawlers.tenkrecipes.config")
    assert sys.modules["models"] is legacy
    assert Path(legacy.__file__).resolve().parent == TOOLS_ROOT / "crawlers/pixabay/src"


def test_documented_plan_example_runs_offline(run_tool, tmp_path):
    """Execute the tool README's plan example instead of matching documentation prose."""
    readme = TOOLS_ROOT / "crawlers/tenkrecipes/README.md"
    documentation = readme.read_text(encoding="utf-8")
    commands = [
        line.strip()
        for block in re.findall(r"```[^\n]*\n(.*?)```", documentation, re.DOTALL)
        for line in block.splitlines()
        if line.strip().startswith("python -m crawlers.tenkrecipes.cli plan ")
    ]
    assert commands, "Document an executable offline plan example"
    for command in commands:
        arguments = shlex.split(command)[3:]
        arguments = [
            str(tmp_path / "documented-run") if value == "{output_dir}" else value
            for value in arguments
        ]
        result = run_tool(*arguments)
        assert result.returncode == 0, result.stdout + result.stderr
        assert json.loads(result.stdout)["total"] == 500
