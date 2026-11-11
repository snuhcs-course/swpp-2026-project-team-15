# AI-assisted with Codex, 2026-11-11; reviewed by Soohyun An
"""Run the future public CLI in an isolated, offline subprocess."""

import json
import os
import socket
import subprocess
import sys
from pathlib import Path

import pytest

TOOLS_ROOT = Path(__file__).resolve().parents[3]
REPO_ROOT = TOOLS_ROOT.parent

BOOTSTRAP = r"""
import atexit
import importlib
import json
import os
from pathlib import Path
import runpy
import sys

tools_root, mode, arguments = sys.argv[1], sys.argv[2], json.loads(sys.argv[3])
sys.path.insert(0, tools_root)
repo_root = Path(tools_root).parent.resolve()
protected = [repo_root / name for name in ('server', 'android', 'data/recipes')]
violations = []

def audit(event, args):
    # Record violations even if the application catches the raised exception.
    forbidden = event in ('socket.connect', 'socket.getaddrinfo', 'subprocess.Popen')
    if event == 'open' and isinstance(args[0], (str, bytes, os.PathLike)):
        path = Path(os.fsdecode(args[0])).resolve()
        forbidden |= any(path == root or root in path.parents for root in protected)
    if forbidden:
        violations.append(event)
        raise RuntimeError('FORBIDDEN_IO: ' + event)

def verify_isolation():
    if violations:
        print('FORBIDDEN_IO: ' + ', '.join(violations), file=sys.stderr, flush=True)
        os._exit(97)

sys.addaudithook(audit)
atexit.register(verify_isolation)
if mode == 'import':
    importlib.import_module('crawlers.tenkrecipes.cli')
elif mode == 'probe':
    import socket
    try:
        socket.getaddrinfo('example.invalid', 443)
    except RuntimeError:
        pass
else:
    sys.argv = ['tenkrecipes', *arguments]
    runpy.run_module('crawlers.tenkrecipes.cli', run_name='__main__')
"""


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """Block parent-process networking as well as the subprocess audit guard."""

    def reject(*args, **kwargs):
        raise AssertionError("Stage 1 tests must not access the network")

    monkeypatch.setattr(socket, "getaddrinfo", reject)
    monkeypatch.setattr(socket.socket, "connect", reject)


@pytest.fixture
def run_tool(tmp_path):
    """Invoke the actual CLI without credentials, network, or production-file access."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    environment = {
        key: value
        for key, value in os.environ.items()
        if key in {"SystemRoot", "WINDIR", "PATH", "TEMP", "TMP", "COMSPEC", "PATHEXT"}
    }
    environment.update(
        PYTHONDONTWRITEBYTECODE="1",
        PYTHONIOENCODING="utf-8",
        NO_COLOR="1",
        TERM="dumb",
    )

    def invoke(*arguments, mode="cli"):
        result = subprocess.run(
            [sys.executable, "-B", "-c", BOOTSTRAP, str(TOOLS_ROOT), mode, json.dumps(arguments)],
            cwd=workspace,
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=20,
            check=False,
        )
        return result

    return invoke
