# AI-assisted with Codex, 2026-11-12; human review pending.
"""Stage 4 acceptance cases directly exercising the approved thumbnail contract."""

import hashlib
import importlib
import io
import os
from pathlib import Path

import pytest
import requests
from PIL import Image

from crawlers.tenkrecipes.config import build_plan
from crawlers.tenkrecipes.tests.stage3_support import (
    FakeTransport,
    client_for,
    fixture_response,
)

IMAGE_URL = "https://recipe1.ezmember.co.kr/cache/recipe/synthetic-first_m.jpg"


def png_bytes(size=(300, 300)):
    """Create a disposable local image, without using downloaded artwork."""
    stream = io.BytesIO()
    Image.new("RGB", size, "green").save(stream, format="PNG")
    return stream.getvalue()


class StreamResponse:
    """Reject eager reads, exposing only a finite chunk stream and response metadata."""

    def __init__(self, body=b"", *, status=200, headers=None, interrupted=False):
        self.body = body
        self.status_code = status
        self.headers = headers or {"Content-Type": "image/png"}
        self.url = None
        self.interrupted = interrupted
        self.closed = False
        self.chunks_read = 0

    @property
    def content(self):
        raise AssertionError("Image transport must read bounded chunks, not eager content")

    def iter_content(self, chunk_size):
        for start in range(0, len(self.body), min(chunk_size, 64)):
            self.chunks_read += 1
            yield self.body[start : start + min(chunk_size, 64)]
            if self.interrupted:
                raise requests.ConnectionError("synthetic stream interruption")

    def close(self):
        self.closed = True


def downloader_for(*responses, **policy):
    """Inject the existing pacing client and stream-only transport into image I/O."""
    module = importlib.import_module("crawlers.tenkrecipes.images")
    _, client, _, clock = client_for()
    transport = FakeTransport(clock, *responses)
    downloader = module.ImageDownloader(client, transport=transport, **policy)
    return module, downloader, client, transport, clock


def make_image_run(tmp_path, *responses):
    """Use real workflow/storage with separate synthetic HTML and image transports."""
    module, downloader, client, transport, clock = downloader_for(*responses)
    workflow = importlib.import_module("crawlers.tenkrecipes.workflow")
    html = FakeTransport(
        clock,
        fixture_response("stage2_list.html"),
        fixture_response("stage2_detail.html"),
        fixture_response("stage2_detail.html"),
    )
    client.transport = html
    options = dict(
        plan=build_plan(tmp_path / "run"),
        client=client,
        image_downloader=downloader,
        parser_version="test-parser-v1",
        schema_version="test-schema-v2",
        utcnow=clock.utcnow,
    )
    run = workflow.CollectionRun.create(**options)
    run.fetch_list("52", 1)
    run.fetch_detail("900001")
    return module, run, options, transport, html


def test_image_decode_preserves_original_bytes_and_300_pixel_dimensions():
    body = png_bytes()
    response = StreamResponse(body)
    _, downloader, _, transport, _ = downloader_for(response)
    result = downloader.get(IMAGE_URL)
    assert result["status"] == "image_validated"
    assert result["body"] == body
    assert result["format"] == "PNG"
    assert (result["width"], result["height"]) == (300, 300)
    assert result["sha256"] == hashlib.sha256(body).hexdigest()
    assert result["source_url"] == result["final_url"] == IMAGE_URL
    assert response.closed
    assert transport.calls[0]["url"] == IMAGE_URL


@pytest.mark.parametrize("body", [b"<html>not an image</html>", b"\x89PNG\r\ntruncated"])
def test_http_200_nonimage_or_corrupt_bytes_are_not_validated(body):
    _, downloader, _, _, _ = downloader_for(StreamResponse(body))
    assert downloader.get(IMAGE_URL)["status"] == "failed"


@pytest.mark.parametrize("advertised", [True, False])
def test_byte_limit_is_enforced_before_unbounded_stream_consumption(advertised):
    headers = {"Content-Type": "image/png"}
    if advertised:
        headers["Content-Length"] = "10000"
    response = StreamResponse(b"x" * 10000, headers=headers)
    _, downloader, _, _, _ = downloader_for(response, max_bytes=100)
    result = downloader.get(IMAGE_URL)
    assert result["status"] == "failed" and result["reason"] == "image_too_large"
    assert response.chunks_read <= (0 if advertised else 2)
    assert response.closed


def test_pixel_limit_rejects_image_without_publishing_it():
    _, downloader, _, _, _ = downloader_for(StreamResponse(png_bytes((30, 30))), max_pixels=100)
    result = downloader.get(IMAGE_URL)
    assert result["status"] == "failed" and result["reason"] == "image_too_many_pixels"


def test_disallowed_redirect_is_rejected_before_target_request():
    response = StreamResponse(status=302, headers={"Location": "https://outside.invalid/image.png"})
    _, downloader, _, transport, _ = downloader_for(response)
    result = downloader.get(IMAGE_URL)
    assert result["status"] == "blocked"
    assert len(transport.calls) == 1


def test_allowed_redirect_keeps_original_url_and_shared_request_pacing():
    first = StreamResponse(status=302, headers={"Location": "/cache/recipe/redirected.png"})
    _, downloader, _, transport, _ = downloader_for(first, StreamResponse(png_bytes()))
    result = downloader.get(IMAGE_URL)
    assert result["status"] == "image_validated"
    assert result["source_url"] == IMAGE_URL
    assert result["final_url"].endswith("/redirected.png")
    assert transport.calls[1]["start"] - transport.calls[0]["start"] >= 2


def test_redirect_limit_stops_before_an_unbounded_loop():
    responses = [StreamResponse(status=302, headers={"Location": IMAGE_URL}) for _ in range(4)]
    _, downloader, _, transport, _ = downloader_for(*responses, max_redirects=1)
    assert downloader.get(IMAGE_URL)["status"] == "blocked"
    assert len(transport.calls) == 2


def test_initial_unlisted_host_is_rejected_without_transport():
    _, downloader, _, transport, _ = downloader_for()
    assert downloader.get("https://outside.invalid/image.png")["status"] == "blocked"
    assert transport.calls == []


def test_selected_thumbnail_is_saved_once_and_identical_bytes_do_not_merge_ids(tmp_path):
    body = png_bytes()
    _, run, options, images, html = make_image_run(
        tmp_path, StreamResponse(body), StreamResponse(body)
    )
    first = run.fetch_thumbnail("900001")
    assert first["status"] == "image_validated"
    root = Path(options["plan"]["output_dir"])
    entry = run.snapshot()["images"]["900001"]
    assert (root / entry["path"]).read_bytes() == body
    assert entry["source_url"] == IMAGE_URL
    assert entry["recipe_source_url"].endswith("/900001")
    assert entry["sha256"] == hashlib.sha256(body).hexdigest()
    run.fetch_thumbnail("900001")
    assert len(images.calls) == 1
    run.fetch_detail("900002")
    run.fetch_thumbnail("900002")
    entries = run.snapshot()["images"]
    assert entries["900001"]["path"] != entries["900002"]["path"]
    assert entries["900001"]["sha256"] == entries["900002"]["sha256"]
    assert len(html.calls) == 3
    assert len(images.calls) == 2
    assert all(
        "icon_vod" not in call["url"] and "step1" not in call["url"] for call in images.calls
    )


def test_interrupted_image_is_not_finalized_and_resume_fetches_only_unfinished_image(tmp_path):
    body = png_bytes()
    _, run, options, images, html = make_image_run(
        tmp_path, *(StreamResponse(body, interrupted=True) for _ in range(3))
    )
    assert run.fetch_thumbnail("900001")["status"] == "failed"
    assert not any(Path(options["plan"]["output_dir"]).glob("images/*.*"))
    images.outcomes.append(StreamResponse(body))
    workflow = importlib.import_module("crawlers.tenkrecipes.workflow")
    resumed = workflow.CollectionRun.resume(**options)
    assert resumed.fetch_thumbnail("900001")["status"] == "image_validated"
    assert len(images.calls) == 4
    assert len(html.calls) == 2


def test_image_published_before_checkpoint_is_reused_after_resume(tmp_path, monkeypatch):
    _, run, options, images, _ = make_image_run(tmp_path, StreamResponse(png_bytes()))
    manifest = Path(options["plan"]["output_dir"]) / "manifest.json"
    replace = os.replace

    def interrupt(source, destination):
        if Path(destination).resolve() == manifest.resolve():
            raise OSError("synthetic interrupted image checkpoint")
        return replace(source, destination)

    with monkeypatch.context() as patch:
        patch.setattr(os, "replace", interrupt)
        with pytest.raises(OSError):
            run.fetch_thumbnail("900001")
    workflow = importlib.import_module("crawlers.tenkrecipes.workflow")
    resumed = workflow.CollectionRun.resume(**options)
    assert resumed.fetch_thumbnail("900001")["status"] == "image_validated"
    assert len(images.calls) == 1


def test_resume_detects_corrupt_validated_image_without_replacing_it(tmp_path):
    _, run, options, images, _ = make_image_run(tmp_path, StreamResponse(png_bytes()))
    run.fetch_thumbnail("900001")
    entry = run.snapshot()["images"]["900001"]
    path = Path(options["plan"]["output_dir"]) / entry["path"]
    path.write_bytes(b"damaged image")
    workflow = importlib.import_module("crawlers.tenkrecipes.workflow")
    with pytest.raises(workflow.IntegrityError):
        workflow.CollectionRun.resume(**options)
    assert path.read_bytes() == b"damaged image"
    assert len(images.calls) == 1


def test_cached_thumbnail_restores_candidate_state_after_rebuilding_parsed_json(tmp_path):
    """Regression: repairing derived JSON must not lose an already validated image state."""
    _, run, options, images, html = make_image_run(tmp_path, StreamResponse(png_bytes()))
    run.fetch_thumbnail("900001")
    root = Path(options["plan"]["output_dir"])
    (root / "recipes/900001.json").unlink()
    workflow = importlib.import_module("crawlers.tenkrecipes.workflow")
    resumed = workflow.CollectionRun.resume(**options)
    resumed.fetch_detail("900001")
    resumed.fetch_thumbnail("900001")
    assert resumed.snapshot()["candidates"][0]["state"] == "image_validated"
    assert len(images.calls) == 1 and len(html.calls) == 2
