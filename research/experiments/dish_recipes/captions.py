# AI-generated with Claude Code (Sonnet 5.5), 2026-11-18; reviewed by Jaehyuk Choi.
"""Stage B helpers: caption text of a video through an UNOFFICIAL route.

The YouTube Data API does not give caption text for videos the caller does not own. This module
uses the `youtube-transcript-api` package (run through `uv run --with youtube-transcript-api`,
never installed globally), which reads the caption track the web player itself uses. That may
conflict with the YouTube terms and can stop working or be blocked at any time. The user
authorised it for a demo only; saved text is not committed.
"""

from __future__ import annotations

from dataclasses import dataclass


class Blocked(Exception):
    """YouTube refused the request (rate limit, IP block, consent wall): stop at once."""


@dataclass(frozen=True)
class Transcript:
    language: str
    kind: str  # "auto" or "manual"
    snippets: list[dict]  # {"start": seconds, "text": str}

    @property
    def chars(self) -> int:
        return sum(len(s["text"]) for s in self.snippets)


def pick_track(tracks: list[tuple[str, bool]]) -> tuple[str, bool] | None:
    """(language, is_generated) to use: Korean manual, Korean auto, then any manual, any auto."""
    for wanted in (
        lambda t: t[0].startswith("ko") and not t[1],
        lambda t: t[0].startswith("ko"),
        lambda t: not t[1],
        lambda t: True,
    ):
        for track in tracks:
            if wanted(track):
                return track
    return None


def clean(text: str) -> str:
    return " ".join(text.replace("\n", " ").split())


def package_errors():
    """The error classes of the caption package (imported late: it is not a project dependency)."""
    import youtube_transcript_api as package

    return package


def fetch_transcript(video_id: str, api=None, errors=None) -> Transcript | None:
    """None when the video has no captions; Blocked when YouTube refuses us."""
    errors = errors or package_errors()
    if api is None:
        api = errors.YouTubeTranscriptApi()
    try:
        listing = list(api.list(video_id))
        track = pick_track([(t.language_code, bool(t.is_generated)) for t in listing])
        if track is None:
            return None
        fetched = api.fetch(video_id, languages=[track[0]])
    except (errors.RequestBlocked, errors.IpBlocked) as error:
        raise Blocked(type(error).__name__) from None
    except (errors.TranscriptsDisabled, errors.NoTranscriptFound, errors.VideoUnavailable):
        return None
    except errors.CouldNotRetrieveTranscript as error:
        if "429" in str(error) or "Too Many" in str(error):
            raise Blocked("rate limited") from None
        return None
    snippets = [
        {"start": round(float(s.start), 1), "text": text}
        for s in fetched.snippets
        if (text := clean(s.text))
    ]
    if not snippets:
        return None
    return Transcript(fetched.language_code, "auto" if fetched.is_generated else "manual", snippets)
