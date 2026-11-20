# AI-generated with Claude Code (Opus 5.5), 2026-11-19; reviewed by Jaehyuk Choi.
import httpx
from experiments.dish_recipes import orientation as o


def test_orientation_from_embed_size():
    assert o.orientation(1000, 1778) == "vertical"
    assert o.orientation(1000, 563) == "horizontal"
    assert o.orientation(500, 500) == "square"
    assert o.orientation(None, 563) == "unknown"
    # the API sends strings; "563" > "1000" as text, so they must be compared as numbers
    assert o.orientation("1000", "563") == "horizontal"
    assert o.orientation("1000", "1778") == "vertical"
    assert o.orientation("x", "1") == "unknown"


def test_fetch_batches_and_marks_missing_ids_unknown():
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        ids = request.url.params["id"].split(",")
        seen.append(len(ids))
        assert request.headers["X-Goog-Api-Key"] == "k"
        assert "key" not in request.url.params
        items = [
            {
                "id": i,
                "player": {"embedWidth": 1000, "embedHeight": 1778 if i.startswith("v") else 563},
            }
            for i in ids
            if i != "gone"
        ]
        return httpx.Response(200, json={"items": items})

    ids = [f"v{n}" for n in range(30)] + [f"h{n}" for n in range(30)] + ["gone"]
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        found = o.fetch(ids, "k", client)
    assert seen == [50, 11]
    assert found["v0"] == "vertical" and found["h0"] == "horizontal" and found["gone"] == "unknown"


def test_summarize_counts_links_first_links_and_recipes():
    dishes = {
        "a": {"videos": [{"id": "v1"}, {"id": "h1"}]},
        "b": {"videos": [{"id": "h1"}]},
        "c": {"videos": [{"id": "v2"}]},
    }
    recipes = {"a": {"video": {"id": "v1"}}, "b": {"video": {"id": "h1"}}}
    by_id = {"v1": "vertical", "v2": "vertical", "h1": "horizontal"}
    s = o.summarize(dishes, recipes, by_id)
    assert s["links"] == 4 and s["distinct_videos"] == 3 and s["distinct_vertical"] == 2
    assert s["links_by_orientation"] == {"vertical": 2, "horizontal": 2}
    assert s["dishes_first_link_vertical"] == ["a", "c"]
    assert s["dishes_only_vertical"] == ["c"]
    assert s["recipes_from_vertical"] == ["a"]
