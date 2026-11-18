# AI-generated with Claude Code (Sonnet 5.5), 2026-11-19; reviewed by Jaehyuk Choi.
"""Contracts of the three video roles: a source proposes, a verifier keeps, a store remembers."""

from datetime import UTC, datetime, timedelta

import httpx
import pytest

from app.dishes.errors import VideoError
from app.dishes.video_search import WebSearchVideoSource
from app.dishes.video_store import VideoStore
from app.dishes.youtube import YouTubeVerifier
from tests.dishes.contracts.fakes import (
    ID_A,
    ID_B,
    FakeStoredVideos,
    FakeVideoSource,
    FakeVideoVerifier,
)

NOW = datetime(2026, 11, 19, tzinfo=UTC)


class VideoSourceContract:
    def make(self, *, fail: bool):
        raise NotImplementedError

    def test_proposes_distinct_video_ids(self):
        ids = self.make(fail=False).propose("김치볶음밥")
        assert ids and len(set(ids)) == len(ids)
        assert all(len(i) == 11 for i in ids)

    def test_a_failed_call_is_a_video_error(self):
        with pytest.raises(VideoError):
            self.make(fail=True).propose("김치볶음밥")


class TestFakeVideoSource(VideoSourceContract):
    def make(self, *, fail):
        return FakeVideoSource([ID_A, ID_B, ID_A], fail=fail)


class TestWebSearchVideoSource(VideoSourceContract):
    def make(self, *, fail):
        def handler(request):
            if fail:
                return httpx.Response(500)
            text = f"https://www.youtube.com/watch?v={ID_A} https://youtu.be/{ID_B} watch?v={ID_A}"
            return httpx.Response(200, json={"choices": [{"message": {"content": text}}]})

        return WebSearchVideoSource("key", transport=httpx.MockTransport(handler))


class VideoVerifierContract:
    def make(self, *, fail: bool):
        raise NotImplementedError

    def test_keeps_a_subset_in_the_order_asked(self):
        videos = self.make(fail=False).check([ID_B, "x" * 11, ID_A])
        ids = [v.video_id for v in videos]
        assert ids == [i for i in [ID_B, ID_A] if i in ids]
        assert set(ids) <= {ID_A, ID_B}

    def test_an_unknown_video_is_dropped_not_an_error(self):
        assert self.make(fail=False).check(["x" * 11]) == []

    def test_a_failed_call_is_a_video_error(self):
        with pytest.raises(VideoError):
            self.make(fail=True).check([ID_A])


class TestFakeVideoVerifier(VideoVerifierContract):
    def make(self, *, fail):
        return FakeVideoVerifier({ID_A, ID_B}, fail=fail)


class TestYouTubeVerifier(VideoVerifierContract):
    def make(self, *, fail):
        def handler(request):
            if fail:
                return httpx.Response(403)
            wanted = request.url.params["id"].split(",")
            items = [
                {"id": i, "snippet": {"title": "t"}, "status": {"embeddable": True}}
                for i in wanted
                if i in (ID_A, ID_B)
            ]
            return httpx.Response(200, json={"items": items})

        return YouTubeVerifier("key", transport=httpx.MockTransport(handler))


class StoredVideosContract:
    def make(self, fetched: datetime):
        raise NotImplementedError

    def test_fresh_entry_in_stored_order(self):
        assert self.make(NOW - timedelta(days=1)).fresh_ids("d", NOW) == [ID_B, ID_A]

    def test_unknown_dish_has_no_ids(self):
        assert self.make(NOW).fresh_ids("other", NOW) == []

    def test_entry_of_thirty_days_is_too_old(self):
        assert self.make(NOW - timedelta(days=30)).fresh_ids("d", NOW) == []


class TestFakeStoredVideos(StoredVideosContract):
    def make(self, fetched):
        return FakeStoredVideos({"d": (fetched, [ID_B, ID_A])})


class TestVideoStore(StoredVideosContract):
    def make(self, fetched):
        entry = {"fetched_at": fetched.isoformat(), "videos": [{"id": ID_B}, {"id": ID_A}]}
        return VideoStore.load_data({"schema": 1, "dishes": {"d": entry}})
