"""The additive review route must get the same gateway treatment as legacy recognition.

AI-assisted, 2026-11-09; manual review pending.
Modified with Claude Code (Opus 5.5), 2026-11-20: the demo gateway has no rate limit on model
routes (owner decision; only the usage upload is limited, ADR 007), so the test now checks that
/analyze/review falls in the same location block, with the same timeout, as /analyze.
"""

import re
from pathlib import Path


def _location_for(text: str, path: str) -> str | None:
    exact = re.findall(r"location\s+=\s+(\S+)\s*\{([^}]+)\}", text)
    for target, body in exact:
        if target == path:
            return body
    regex = re.findall(r"location\s+~\s+(\S+)\s*\{([^}]+)\}", text)
    for pattern, body in regex:
        if re.search(pattern, path):
            return body
    prefix = re.findall(r"location\s+(/\S*)\s*\{([^}]+)\}", text)
    best = max(
        ((p, b) for p, b in prefix if path.startswith(p)), default=None, key=lambda x: len(x[0])
    )
    return best[1] if best else None


def test_review_uses_the_same_gateway_rules_and_timeout_as_legacy_recognition():
    config = Path(__file__).resolve().parents[3] / "deploy" / "nginx.conf"
    text = config.read_text(encoding="utf-8")
    legacy = _location_for(text, "/analyze")
    assert legacy is not None
    assert "proxy_read_timeout 210s" in legacy
    assert _location_for(text, "/analyze/review") == legacy
