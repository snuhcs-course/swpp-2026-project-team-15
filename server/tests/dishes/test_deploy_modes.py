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


def test_release_script_deploys_the_database_free_stack():
    # Auto-deploy kept from main (2026-11-20) and adapted: keys, data and usage file live outside
    # the release checkout, only api and nginx are (re)started, and an old postgres is left alone.
    script = (ROOT / "deploy/release.sh").read_text(encoding="utf-8")
    assert "set -euo pipefail" in script
    for setting in (
        'RUNTIME_ENV="$ROOT/config/runtime-dishes.env"',
        'DISH_DATA_DIR="$ROOT/data/dish-data"',
        'TELEMETRY_DIR="$ROOT/data/telemetry"',
        "HTTP_PORT=80",
    ):
        assert setting in script
    code = "\n".join(line for line in script.splitlines() if not line.lstrip().startswith("#"))
    candidate = code.split("for attempt", 1)[0]
    assert "postgres" not in candidate and "DATABASE" not in candidate
    assert "docker compose up -d --no-deps api" in candidate
    assert "--remove-orphans" not in script and " down" not in script


def test_auto_deploy_runs_the_release_script_for_green_main_pushes():
    workflow = (ROOT / ".github/workflows/deploy.yml").read_text(encoding="utf-8")
    assert "workflows: [ci]" in workflow and "branches: [main]" in workflow
    assert 'bash "$path/deploy/release.sh" "$sha"' in workflow
    assert "merge-base --is-ancestor" in workflow
