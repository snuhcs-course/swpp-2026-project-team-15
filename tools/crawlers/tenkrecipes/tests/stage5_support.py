# AI-assisted with Codex, 2026-11-12; human review pending.
"""Synthetic source inputs and saved artifacts, without allocation/report logic."""

import copy
import json
from urllib.parse import parse_qs, urlsplit

from bs4 import BeautifulSoup

from crawlers.tenkrecipes.config import build_plan
from crawlers.tenkrecipes.images import ImageDownloader
from crawlers.tenkrecipes.parsing import parse_recipe
from crawlers.tenkrecipes.storage import digest
from crawlers.tenkrecipes.tests.stage3_support import FIXTURES, FakeResponse, client_for
from crawlers.tenkrecipes.tests.test_stage4_images import StreamResponse, png_bytes
from crawlers.tenkrecipes.workflow import PARSER_VERSION, SCHEMA_VERSION, CollectionRun


def list_html(category, ids):
    """Render ordered synthetic cards; an empty input is a valid exhausted page."""
    cards = "".join(
        f'<li class="common_sp_list_li"><div class="common_sp_thumb">'
        f'<a class="common_sp_link" href="/recipe/{source_id}">'
        f'<img src="https://recipe1.ezmember.co.kr/{source_id}.png"></a></div>'
        '<div class="common_sp_caption_tit">Same dish</div></li>'
        for source_id in ids
    )
    return (
        f'<form><input name="cat2" value="18"><input name="cat4" value="{category}">'
        '<input name="order" value="reco"></form>'
        f'<div class="recipe_result">총 {len(ids)}개의 맛있는 레시피가 있습니다.</div>'
        f'<ul class="common_sp_list_ul">{cards}</ul>'
    ).encode()


def detail_html(missing=None):
    """Remove content while retaining containers, or deliberately break structure."""
    soup = BeautifulSoup(
        (FIXTURES / "stage2_detail.html").read_text(encoding="utf-8"), "html.parser"
    )
    if missing == "title":
        soup.select_one(".view2_summary h3").clear()
    elif missing in ("ingredients", "ingredient_names"):
        selector = "#divConfirmedMaterialArea" if missing == "ingredients" else ".ingre_list_name"
        for node in soup.select(selector):
            node.clear()
    elif missing in ("steps", "instructions"):
        selector = ".view_step" if missing == "steps" else '[id^="stepdescr"]'
        for node in soup.select(selector):
            node.clear()
    elif missing == "structure":
        soup.select_one("#divConfirmedMaterialArea").decompose()
    return str(soup).encode()


def scripted_run(tmp_path, pages, *, details=None, image_failures=()):
    """Route fake HTTP by URL; production code must decide traversal and selection."""
    _, client, _, clock = client_for(run_budget=100000)
    calls = []
    details = details or {}

    def html_transport(url, **kwargs):
        calls.append(url)
        parts = urlsplit(url)
        if parts.path.endswith("list.html"):
            query = parse_qs(parts.query)
            assert query["cat2"] == ["18"] and query["order"] == ["reco"]
            category, page = query["cat4"][0], int(query["page"][0])
            assert page <= 4, "Traversal must stop on exhaustion or repeated pages"
            outcome = pages.get((category, page), [])
            if isinstance(outcome, FakeResponse):
                outcome.url = url
                return outcome
            return FakeResponse(body=list_html(category, outcome), url=url)
        source_id = parts.path.rsplit("/", 1)[-1]
        return FakeResponse(body=details.get(source_id, detail_html()), url=url)

    def image_transport(url, **kwargs):
        calls.append(url)
        source_id = urlsplit(url).path.strip("/").removesuffix(".png")
        response = StreamResponse(b"not an image" if source_id in image_failures else png_bytes())
        response.url = url
        return response

    client.transport = html_transport
    options = dict(
        plan=build_plan(tmp_path / "run"),
        client=client,
        image_downloader=ImageDownloader(client, transport=image_transport),
        parser_version=PARSER_VERSION,
        schema_version=SCHEMA_VERSION,
        utcnow=clock.utcnow,
    )
    return CollectionRun.create(**options), options, calls


def saved_collection(tmp_path):
    """Write 500 explicitly allocated records for offline report validation tests.

    This fixture declares a completed input, not a collector or a completion
    oracle. All IDs deliberately have identical content and image bytes.
    """
    run, _, calls = scripted_run(tmp_path, {})

    def save_fixture(path, content):
        # Fixture setup does not exercise crash-safe publication (stage 3).
        destination = run.storage.root / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)

    manifest = run.snapshot()
    manifest.update(allocations=[], failures=[], replacements=[], category_outcomes=[])
    body, image = detail_html(), png_bytes()
    template = parse_recipe(body.decode(), source_url="https://www.10000recipe.com/recipe/900000")
    for category in run.metadata["plan"]["categories"]:
        code = category["cat4"]
        ids = [str(900000 + len(manifest["allocations"]) + i) for i in range(category["quota"])]
        raw_list = list_html(code, ids)
        list_path = f"lists/{code}/1.html"
        save_fixture(list_path, raw_list)
        manifest["lists"].append(
            dict(
                path=list_path,
                sha256=digest(raw_list),
                category_code=code,
                page=1,
                source_url=category["list_url"],
                final_url=category["list_url"],
                fetched_at=run.metadata["started_at"],
            )
        )
        for position, source_id in enumerate(ids, 1):
            url = f"https://www.10000recipe.com/recipe/{source_id}"
            raw = dict(path=f"details/{source_id}.html", sha256=digest(body), source_url=url)
            save_fixture(raw["path"], body)
            record = copy.deepcopy(template)
            record["source"].update(id=source_id, url=url)
            # Missing tool registration is review information, never a rejection.
            record["listed_tools"] = None
            path = f"recipes/{source_id}.json"
            record_bytes = json.dumps(record, ensure_ascii=False).encode("utf-8")
            save_fixture(path, record_bytes)
            manifest["details"][source_id] = dict(
                state="parsed",
                source_url=url,
                raw=raw,
                record=dict(path=path, sha256=digest(record_bytes)),
            )
            image_path = f"images/{source_id}.png"
            save_fixture(image_path, image)
            manifest["images"][source_id] = dict(
                state="image_validated",
                path=image_path,
                sha256=digest(image),
                source_id=source_id,
                recipe_source_url=url,
                source_url=f"https://recipe1.ezmember.co.kr/{source_id}.png",
                format="PNG",
                width=300,
                height=300,
                byte_count=len(image),
            )
            manifest["allocations"].append(dict(source_id=source_id, category_code=code))
            manifest["candidates"].append(
                dict(
                    source_id=source_id,
                    source_url=url,
                    category_code=code,
                    page=1,
                    position=position,
                    state="selected",
                    thumbnail_url=manifest["images"][source_id]["source_url"],
                )
            )
    run.storage.write_json("manifest.json", manifest)
    assert calls == []
    return run.storage, copy.deepcopy(manifest)
