# AI-assisted with Codex, 2026-11-11; reviewed by Soohyun An
"""Task 3.2/3.5: live command gates and help must be testable without live I/O."""

import pytest


@pytest.mark.parametrize("command", ["collect", "resume"])
def test_live_command_help_is_available_offline(run_tool, command):
    result = run_tool(command, "--help")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "--live" in result.stdout + result.stderr
    assert "FORBIDDEN_IO" not in result.stderr


@pytest.mark.parametrize("command", ["collect", "resume"])
def test_live_commands_reject_missing_live_before_network_or_run_creation(
    run_tool, tmp_path, command
):
    output = tmp_path / "new-run"
    arguments = [command, "--output-dir", str(output)]
    result = run_tool(*arguments)
    assert result.returncode != 0
    diagnostic = result.stdout + result.stderr
    assert "No such command" not in diagnostic
    assert "--live" in diagnostic
    assert "FORBIDDEN_IO" not in result.stderr
    assert not output.exists()
