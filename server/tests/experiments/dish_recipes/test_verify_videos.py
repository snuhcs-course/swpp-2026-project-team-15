# AI-generated with Claude Code (Opus 5.5), 2026-11-19; reviewed by Jaehyuk Choi.
"""Offline tests of the stored-video verification (no network)."""

from experiments.dish_recipes import verify_videos as vv


def _item(vid: str, privacy="public", embeddable=True, duration="PT4M12S") -> dict:
    return {
        "id": vid,
        "snippet": {
            "title": "김치볶음밥",
            "channelTitle": "c",
            "description": "x" * 900,
            "tags": ["a"],
        },
        "contentDetails": {"duration": duration},
        "statistics": {"viewCount": "12"},
        "status": {"privacyStatus": privacy, "embeddable": embeddable, "uploadStatus": "processed"},
    }


def test_iso_duration():
    assert vv.iso_seconds("PT4M12S") == 252
    assert vv.iso_seconds("PT1H2M") == 3720
    assert vv.iso_seconds("P1DT1S") == 86401
    assert vv.iso_seconds("bad") is None


def test_to_video_truncates_description_and_checks_playability():
    v = vv.to_video(_item("abc"))
    assert len(v["description"]) == vv.DESCRIPTION_CHARS and v["duration_s"] == 252
    assert vv.playable(v)
    assert not vv.playable(vv.to_video(_item("p", privacy="private")))
    assert not vv.playable(vv.to_video(_item("e", embeddable=False)))
    assert not vv.playable(None)


def test_parse_judgements_requires_exact_keys():
    text = '{"judgements":[{"i":"a|1","relevant":true,"reason":"ok"},{"i":"a|2","relevant":false}]}'
    assert vv.parse_judgements(text, ["a|1", "a|2"])["a|2"]["relevant"] is False
    assert vv.parse_judgements(text, ["a|1"]) is None
    assert vv.parse_judgements("no json", ["a|1"]) is None


def _pair(a, b):
    return {"judges": {vv.JUDGES[0]: {"relevant": a}, vv.JUDGES[1]: {"relevant": b}}}


def test_review_queue_and_decision():
    pairs = {f"d|{n}": _pair(True, True) for n in range(20)}
    pairs["d|x"] = _pair(True, False)
    pairs["d|y"] = _pair(False, False)
    pairs["d|z"] = {"judges": {}}
    q = vv.review_queue(pairs, seed=1)
    assert q["d|x"] == "disagree_or_missing" and q["d|z"] == "disagree_or_missing"
    assert q["d|y"] == "primary_no"
    assert sum(w == "agreed_sample" for w in q.values()) == 2  # 10% of 20 agreed pairs
    assert vv.review_queue(pairs, seed=1) == q  # seeded
    assert vv.decide(pairs["d|0"], None, None) == (True, "both_judges")
    assert vv.decide(pairs["d|y"], "primary_no", None) == (False, "unreviewed")
    assert vv.decide(pairs["d|y"], "primary_no", {"decision": "relevant"})[0] is True
    assert vv.decide(pairs["d|0"], "agreed_sample", {"decision": "unsure"})[0] is False
