# AI-generated with Claude Code (Sonnet 5.5), 2026-11-16; reviewed by Jaehyuk Choi.
"""Deployment pieces of the dish server: DISH_ONLY mode, cache reload, packaging, nginx."""

import importlib.util
import json
import os
import re
import time
from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

from app.dishes.prefetch import main as prefetch_main
from app.dishes.youtube import VideoCache

ROOT = Path(__file__).resolve().parents[3]


def _env(monkeypatch, tmp_path, **extra):
    for name in ("DATABASE_URL", "OPENROUTER_API_KEY", "DISH_LLM_API_KEY", "RECIPE_DB_OPTIONAL"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("VISION_PROVIDER", "mock")
    monkeypatch.setenv("RECIPE_DB_PATH", str(tmp_path / "recipes.sqlite3"))
    for name, value in extra.items():
        monkeypatch.setenv(name, value)


def test_dish_only_ignores_a_broken_recipe_database(tmp_path, monkeypatch):
    from app.main import create_app_from_env

    (tmp_path / "recipes.sqlite3").write_bytes(b"this is not a database")
    _env(monkeypatch, tmp_path, DISH_ONLY="1")
    client = TestClient(create_app_from_env())
    assert client.get("/ready").json() == {"status": "ready"}
    assert client.get("/dishes").json()["count"] >= 100
    assert client.post("/recipes/recommend", json={"ingredients": ["계란"]}).status_code == 404


def test_dish_only_does_not_connect_to_a_configured_postgres(tmp_path, monkeypatch):
    from app.main import create_app_from_env

    _env(monkeypatch, tmp_path, DISH_ONLY="1")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://chef:x@192.0.2.1:5432/chef")
    started = time.monotonic()
    client = TestClient(create_app_from_env())
    assert client.get("/ready").status_code == 200
    assert time.monotonic() - started < 5  # no connection attempt (192.0.2.1 never answers)


def test_dish_only_off_keeps_the_database_required(tmp_path, monkeypatch):
    import pytest

    from app.main import create_app_from_env

    _env(monkeypatch, tmp_path, DISH_ONLY="0")
    with pytest.raises(FileNotFoundError):
        create_app_from_env()


def test_cache_picks_up_a_file_replaced_by_a_refresh_job(tmp_path):
    path = tmp_path / "videos.json"
    cache = VideoCache(path)
    assert cache.get("kimchi-fried-rice") == []  # no file yet
    entry = {
        "fetched_at": datetime.now(UTC).isoformat(),
        "videos": [{"video_id": "x" * 11, "title": "t", "channel": "c"}],
    }
    path.write_text(json.dumps({"kimchi-fried-rice": entry}), encoding="utf-8")
    os.utime(path, (time.time() + 5, time.time() + 5))  # a distinct mtime on coarse filesystems
    assert cache.get("kimchi-fried-rice")[0]["video_id"] == "x" * 11
    path.unlink()
    assert cache.get("kimchi-fried-rice") == []  # removed file: back to empty, no error


def test_prefetch_module_is_a_dry_run_without_live(tmp_path, capsys):
    assert prefetch_main(["--cache", str(tmp_path / "videos.json"), "--max-requests", "4"]) == 0
    out = capsys.readouterr().out
    assert "dry run" in out and "quota_units" in out
    assert not (tmp_path / "videos.json").exists()


def test_runtime_archive_and_image_carry_the_dish_data():
    spec = importlib.util.spec_from_file_location(
        "package_server", ROOT / "scripts/package_server.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    data = "server/app/dishes/dishes.json"
    assert (ROOT / data).is_file()
    assert data.startswith(module.RUNTIME_DIRECTORIES)
    assert "server/app/dishes/prefetch.py".startswith(module.RUNTIME_DIRECTORIES)
    assert "!server/app/**" in (ROOT / ".dockerignore").read_text().splitlines()
    assert "COPY server/app ./app" in (ROOT / "Dockerfile").read_text().splitlines()


def test_nginx_rate_limits_the_paid_dish_routes():
    conf = (ROOT / "deploy/nginx.conf").read_text(encoding="utf-8")
    block = re.search(r"location ~ \^/\(([^)]*)\)\$ \{([^}]*)\}", conf)
    routes = block.group(1).split("|")
    assert {"analyze", "recipes/recommendations", "dishes/suggest", "dishes/adapt"} <= set(routes)
    assert "limit_req zone=ai" in block.group(2)
