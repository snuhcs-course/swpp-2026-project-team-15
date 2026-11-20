# AI-generated with Claude Code (Sonnet 5.5), 2026-11-16; reviewed by Jaehyuk Choi.
"""Deployment pieces of the dish server: packaging and nginx."""

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_runtime_archive_and_image_carry_the_dish_data():
    spec = importlib.util.spec_from_file_location(
        "package_server", ROOT / "scripts/package_server.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    data = "server/app/dishes/dishes.json"
    assert (ROOT / data).is_file()
    assert data.startswith(module.RUNTIME_DIRECTORIES)
    assert "server/app/dishes/videos.py".startswith(module.RUNTIME_DIRECTORIES)
    assert "!server/app/**" in (ROOT / ".dockerignore").read_text().splitlines()
    assert "COPY server/app ./app" in (ROOT / "Dockerfile").read_text().splitlines()


def test_nginx_limits_only_the_usage_upload():
    # Model routes stay unlimited (demo); only the usage upload is rate-limited (ADR 007).
    conf = (ROOT / "deploy/nginx.conf").read_text(encoding="utf-8")
    assert "limit_conn" not in conf
    assert conf.count("location ") == 2 and "location = /telemetry/events {" in conf
    general = conf.split("location / {", 1)[1]
    assert "limit_req" not in general
    assert "limit_req zone=telemetry" in conf.split("location = /telemetry/events {", 1)[1]
    assert "client_max_body_size 16m;" in conf and "proxy_read_timeout 210s;" in conf
