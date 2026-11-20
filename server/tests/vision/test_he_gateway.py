"""The additive review route must inherit existing paid-vision gateway protection.

AI-assisted, 2026-11-09; manual review pending.
"""

import re
from pathlib import Path


def test_review_uses_the_same_rate_limit_and_timeout_as_legacy_recognition():
    config = Path(__file__).resolve().parents[3] / "deploy" / "nginx.conf"
    text = config.read_text(encoding="utf-8")
    blocks = re.findall(r"location\s+~\s+(\S+)\s*\{([^}]+)\}", text)

    def ai_block(path):
        return next((body for pattern, body in blocks if re.search(pattern, path)), None)

    legacy = ai_block("/analyze")
    assert legacy is not None
    assert "limit_req zone=ai" in legacy
    assert "proxy_read_timeout 210s" in legacy
    assert ai_block("/analyze/review") == legacy
    assert ai_block("/recipes/recommendations") == legacy
    assert ai_block("/recipes/recommend") is None
