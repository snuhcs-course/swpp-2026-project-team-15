# AI-generated with Claude Code (Opus 5.5), 2026-10-11; reviewed by Jaehyuk Choi.
from tests.conftest import StubVision


def test_health(make_client):
    assert make_client(StubVision()).get("/health").json() == {"status": "ok"}
