# AI-generated with Claude Code (Opus 5.5), 2026-11-20; reviewed by Jaehyuk Choi.
"""The app's event names and field values must be ones the server accepts (no silent 422s)."""

import re
from pathlib import Path
from typing import get_args

from app.telemetry.schemas import EventName, Screen, Source, Status

ANDROID = Path(__file__).resolve().parents[3] / "android/app/src/main/java/com/example/mylittlechef"


def test_app_event_names_are_the_servers():
    source = (ANDROID / "domain/Telemetry.kt").read_text(encoding="utf-8")
    assert set(re.findall(r'[A-Z_]+\("([a-z_]+)"\)', source)) == set(get_args(EventName))


def test_app_statuses_sources_and_screens_are_accepted():
    text = "\n".join(p.read_text(encoding="utf-8") for p in ANDROID.rglob("*.kt"))
    statuses = set(re.findall(r'status = "([a-z_]+)"', text)) | set(
        re.findall(r'-> "(ok|empty|error|revised|refused|failed)"', text)
    )
    assert statuses and statuses <= set(get_args(Status))
    sources = set(re.findall(r'source = "([a-z_]+)"', text))
    assert sources and sources <= set(get_args(Source))
    screens = set(
        re.findall(
            r'-> "(onboarding|fridge|dishes|profile|capture|analyze|manual_add|\w+)"\n', text
        )
    )
    screen_lines = re.findall(r'Routes\.\w+ -> "([a-z_]+)"', text)
    assert screen_lines and set(screen_lines) <= set(get_args(Screen)), (screens, screen_lines)
