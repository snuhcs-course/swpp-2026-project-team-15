# AI-generated with Claude Code (Sonnet 5.5), 2026-11-16; reviewed by Jaehyuk Choi.
"""Deployment pieces of the dish server: cache reload, packaging, nginx."""

import importlib.util
import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path

from app.dishes.prefetch import main as prefetch_main
from app.dishes.youtube import VideoCache

ROOT = Path(__file__).resolve().parents[3]


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


def test_nginx_has_one_proxy_location_and_no_rate_limit():
    conf = (ROOT / "deploy/nginx.conf").read_text(encoding="utf-8")
    assert "limit_req" not in conf and "limit_conn" not in conf
    assert conf.count("location ") == 1
    assert "client_max_body_size 16m;" in conf and "proxy_read_timeout 210s;" in conf
