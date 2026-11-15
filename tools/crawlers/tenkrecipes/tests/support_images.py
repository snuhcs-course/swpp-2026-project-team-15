# AI-assisted with Codex, 2026-11-15; reviewed by Soohyun An
"""Synthetic image streams and constructors shared by acquisition tests."""

import importlib
import io

import requests
from PIL import Image

from crawlers.tenkrecipes.config import build_plan
from crawlers.tenkrecipes.tests.support_http import FakeTransport, client_for, fixture_response


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
        fixture_response("list.html"),
        fixture_response("detail.html"),
        fixture_response("detail.html"),
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
