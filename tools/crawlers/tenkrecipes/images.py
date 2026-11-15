# AI-assisted with Codex, 2026-11-12; reviewed by Soohyun An
"""Bounded thumbnail streams with explicit redirects and original-byte validation."""

import hashlib
import io
import tempfile
import warnings
from urllib.parse import urljoin, urlsplit

import requests
from PIL import Image, UnidentifiedImageError

DEFAULT_HOSTS = ("recipe1.ezmember.co.kr", "www.10000recipe.com", "10000recipe.com")


class ImageTransferError(requests.RequestException):
    """An image stream exceeded a resource bound before it could be published."""


def request_image(url, *, timeout, headers):
    """Open a streamed, credential-free response; its owner must close it."""
    session = requests.Session()
    session.trust_env = False
    try:
        response = session.get(
            url, timeout=timeout, headers=headers, stream=True, allow_redirects=False
        )
    except BaseException:
        session.close()
        raise
    close_response = response.close

    def close():
        close_response()
        session.close()

    response.close = close
    return response


class BoundedResponse:
    """Expose response bytes only after a finite, temporary-file-backed read."""

    def __init__(self, response, max_bytes):
        self.response = response
        self.max_bytes = max_bytes
        self.status_code, self.headers, self.url = (
            response.status_code,
            response.headers,
            response.url,
        )

    @property
    def content(self):
        try:
            length = self.headers.get("Content-Length")
            if length and length.isdecimal() and int(length) > self.max_bytes:
                raise ImageTransferError("image_too_large")
            size = 0
            with tempfile.TemporaryFile() as temporary:
                for chunk in self.response.iter_content(chunk_size=64 * 1024):
                    size += len(chunk)
                    if size > self.max_bytes:
                        raise ImageTransferError("image_too_large")
                    temporary.write(chunk)
                temporary.seek(0)
                return temporary.read()
        finally:
            self.response.close()


class ImageDownloader:
    """Share source request pacing/retry budgets while enforcing image-specific bounds.

    Defaults are resource limits for collection, not recipe suitability rules.
    The source URL is never rewritten to infer a different-resolution asset.
    """

    def __init__(
        self,
        client,
        *,
        transport=request_image,
        allowed_hosts=DEFAULT_HOSTS,
        max_bytes=10 * 1024 * 1024,
        max_pixels=20_000_000,
        max_redirects=3,
    ):
        for value in (max_bytes, max_pixels):
            if type(value) is not int or value <= 0:
                raise ValueError("Image byte/pixel limits must be positive integers")
        if type(max_redirects) is not int or max_redirects < 0:
            raise ValueError("Image redirect limit must be a nonnegative integer")
        self.client, self.transport = client, transport
        self.policy = dict(
            allowed_hosts=list(allowed_hosts),
            max_bytes=max_bytes,
            max_pixels=max_pixels,
            max_redirects=max_redirects,
        )

    def _validate_url(self, url):
        parts = urlsplit(url)
        if (
            parts.scheme not in ("http", "https")
            or parts.hostname not in self.policy["allowed_hosts"]
            or parts.username is not None
            or parts.password is not None
            or parts.port not in (None, 80, 443)
        ):
            raise ValueError("Image URL is outside configured hosts")
        return url

    def get(self, url):
        """Return validated original bytes or a recorded failure, never a partial image."""
        original, current = url, url
        attempts, responses = [], []
        for redirect in range(self.policy["max_redirects"] + 1):
            try:
                self._validate_url(current)
            except ValueError:
                return dict(
                    status="blocked",
                    reason="image_host_not_allowed",
                    attempts=attempts,
                    responses=responses,
                    body=None,
                )
            metadata = {}

            def bounded_transport(target, *, timeout, headers, metadata=metadata):
                response = self.transport(target, timeout=timeout, headers=headers)
                metadata.update(
                    location=response.headers.get("Location"),
                    content_type=response.headers.get("Content-Type", ""),
                )
                return BoundedResponse(response, self.policy["max_bytes"])

            result = self.client.get(
                current, validator=self._validate_url, transport=bounded_transport
            )
            attempts.extend(result["attempts"])
            responses.extend(result["responses"])
            result.update(attempts=list(attempts), responses=list(responses))
            if any(row.get("error") == "ImageTransferError" for row in result["attempts"]):
                return dict(result, status="failed", reason="image_too_large")
            status_code = result["attempts"][-1].get("status_code") if result["attempts"] else None
            if status_code in (301, 302, 303, 307, 308) and metadata.get("location"):
                if redirect == self.policy["max_redirects"]:
                    return dict(result, status="blocked", reason="image_redirect_limit")
                current = urljoin(current, metadata["location"])
                continue
            if result["status"] != "ok":
                return result
            try:
                dimensions = self.validate(result["body"])
            except (
                OSError,
                ValueError,
                Image.DecompressionBombError,
                Image.DecompressionBombWarning,
            ) as exc:
                reason = (
                    "image_too_many_pixels"
                    if isinstance(exc, Image.DecompressionBombError)
                    else "invalid_image"
                )
                return dict(result, status="failed", reason=reason)
            return dict(
                result,
                status="image_validated",
                source_url=original,
                final_url=current,
                sha256=hashlib.sha256(result["body"]).hexdigest(),
                content_type=metadata["content_type"],
                byte_count=len(result["body"]),
                fetched_at=attempts[-1]["fetched_at"],
                **dimensions,
            )
        raise AssertionError("Unreachable redirect loop")

    def validate(self, body):
        """Verify image structure and decode pixels without resizing or re-encoding."""
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(body)) as image:
                width, height = image.size
                if width * height > self.policy["max_pixels"]:
                    raise Image.DecompressionBombError("Configured image pixel limit exceeded")
                image_format = image.format
                image.verify()
            with Image.open(io.BytesIO(body)) as image:
                image.load()
        if not image_format:
            raise UnidentifiedImageError("Missing decoded image format")
        return dict(format=image_format, width=width, height=height)
