# AI-assisted with Codex, 2026-11-11; reviewed by Soohyun An
"""Offline extraction of source observations; no service normalization or fetching."""

import copy
import html as html_module
import json
import re
import unicodedata
from urllib.parse import parse_qs, urljoin, urlsplit

from bs4 import BeautifulSoup, Tag


class ParseError(ValueError):
    """The input URL, source filters, or required HTML structure is unrecognized."""


def _text(node: Tag | None) -> str | None:
    """Extract readable DOM text without interpreting quantities or units."""
    if node is None:
        return None
    return node.get_text(" ", strip=True) or None


def _recipe_identity(source_url: str) -> tuple[str, str]:
    """Validate a recipe link and return its source ID and canonical URL."""
    parsed = urlsplit(source_url)
    match = re.fullmatch(r"/recipe/(\d+)/?", parsed.path)
    if (
        parsed.scheme not in ("http", "https")
        or parsed.hostname not in ("www.10000recipe.com", "10000recipe.com")
        or not match
    ):
        raise ParseError(f"Unrecognized recipe URL: {source_url}")
    source_id = match.group(1)
    return source_id, f"https://www.10000recipe.com/recipe/{source_id}"


def _absolute_url(value: str | None, source_url: str) -> str | None:
    """Resolve source asset references without opening them."""
    if not value:
        return None
    url = urljoin(source_url, value.strip())
    return url if urlsplit(url).scheme in ("http", "https") else None


def parse_list_page(html: str, *, source_url: str) -> dict:
    """Parse a filtered list snapshot, retaining page-local duplicate observations.

    A recognized container plus an explicit zero result count is required for an
    empty result. Missing cards otherwise indicate layout drift, not exhaustion.
    """
    soup = BeautifulSoup(html, "html.parser")
    query = parse_qs(urlsplit(source_url).query)
    for key in ("cat2", "cat4", "order"):
        requested = query.get(key, [])
        control = soup.select_one(f'[name="{key}"]')
        if control is not None and control.name == "select":
            control = control.select_one("option[selected]")
        if len(requested) != 1 or control is None or control.get("value") != requested[0]:
            raise ParseError(f"Missing or mismatched list filter: {key}")
    if query["cat2"] != ["18"] or query["order"] != ["reco"]:
        raise ParseError("Expected quick-recipe filters and recommendation order")
    try:
        page_values = query.get("page", ["1"])
        page = int(page_values[0]) if len(page_values) == 1 else 0
        if page < 1:
            raise ValueError
    except ValueError as exc:
        raise ParseError("Invalid list page number") from exc
    container = soup.select_one(".common_sp_list_ul")
    if container is None:
        raise ParseError("Missing recipe list container")
    cards = container.select(".common_sp_list_li")
    if not cards and not re.search(r"총\s*0\s*개", soup.get_text(" ", strip=True)):
        raise ParseError("Missing recipe cards without explicit empty result")
    items = []
    for position, card in enumerate(cards, 1):
        link = card.select_one(".common_sp_thumb .common_sp_link[href]")
        title = _text(card.select_one(".common_sp_caption_tit"))
        if link is None or not title:
            raise ParseError("Missing candidate link or title")
        candidate_url = urljoin(source_url, link["href"])
        source_id, candidate_url = _recipe_identity(candidate_url)
        # Badges are nested inside spans; the recipe image belongs to the link.
        image = link.find("img", recursive=False)
        thumbnail = (
            _absolute_url(image.get("data-src") or image.get("src"), source_url)
            if image is not None
            else None
        )
        if thumbnail is None:
            raise ParseError("Missing recipe thumbnail")
        items.append(
            dict(
                position=position,
                source_id=source_id,
                source_url=candidate_url,
                title=title,
                thumbnail_url=thumbnail,
            )
        )
    return dict(
        status="ok" if items else "empty",
        source_url=source_url,
        page=page,
        category_code=query["cat4"][0],
        items=items,
    )


def _recipe_nodes(value):
    """Yield Recipe objects from JSON-LD objects, arrays, and graph wrappers."""
    if isinstance(value, list):
        for item in value:
            yield from _recipe_nodes(item)
    elif isinstance(value, dict):
        types = value.get("@type", [])
        if isinstance(types, str):
            types = [types]
        if isinstance(types, list) and "Recipe" in types:
            yield value
        if "@graph" in value:
            yield from _recipe_nodes(value["@graph"])


def _metadata(soup: BeautifulSoup) -> dict:
    """Find the first usable Recipe object without depending on script position."""
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            value = json.loads(script.get_text())
        except (ValueError, TypeError):
            continue
        recipe = next(_recipe_nodes(value), None)
        if recipe is not None:
            return recipe
    return {}


def _string(value) -> str | None:
    return value if isinstance(value, str) and value.strip() else None


def _ingredients(area: Tag, findings: list) -> list[dict]:
    """Keep source rows, separating nested notes from names and quantities."""
    result = []
    for group in area.select("ul"):
        label = _text(group.select_one(".ready_ingre3_tt"))
        for row in group.find_all("li", recursive=False):
            name_node = row.select_one(".ingre_list_name")
            if name_node is None:
                raise ParseError("Missing ingredient name element")
            name_copy = copy.copy(name_node)
            notes = []
            for span in list(name_copy.select("span")):
                if span.parent is not None:
                    note = _text(span)
                    if note:
                        notes.append(note)
                    span.decompose()
            source_id = None
            for anchor in name_node.select("a"):
                match = re.search(r"viewMaterial\(['\"](\d+)['\"]", str(anchor.get("href", "")))
                if match:
                    source_id = match.group(1)
                    break
            quantity = _text(row.select_one(".ingre_list_ea"))
            order = len(result) + 1
            result.append(
                dict(
                    group=label,
                    order=order,
                    name_raw=_text(name_copy),
                    note_raw=" ".join(notes) or None,
                    quantity_text=quantity,
                    source_material_id=source_id,
                )
            )
            if quantity is None:
                findings.append(dict(code="missing_quantity", field="ingredients", order=order))
    return result


def _steps(soup: BeautifulSoup, source_url: str) -> list[dict]:
    """Extract ordered step bodies and tips separately, retaining repeated text."""
    result = []
    for step in soup.select(".view_step .view_step_cont"):
        body = step.select_one('[id^="stepdescr"]')
        if body is None:
            raise ParseError("Missing step instruction element")
        tips = [text for tip in step.select(".step_add") if (text := _text(tip))]
        body_copy = copy.copy(body)
        for tip in body_copy.select(".step_add"):
            tip.decompose()
        images = []
        for image in step.select("img"):
            url = _absolute_url(image.get("data-src") or image.get("src"), source_url)
            if url:
                images.append(url)
        result.append(
            dict(order=len(result) + 1, instruction=_text(body_copy), tips=tips, image_urls=images)
        )
    return result


def _listed_tools(soup: BeautifulSoup, source_url: str) -> list[dict] | None:
    """Use only the explicitly labeled tool section, never actions or reviews."""
    for heading in soup.select(".best_tit"):
        if _text(heading) != "조리도구":
            continue
        section = heading.find_next_sibling()
        if section is None or "ready_ingre3" not in section.get("class", []):
            raise ParseError("Missing listed-tool section body")
        return [
            dict(name_raw=name, evidence=dict(source_url=source_url, section="조리도구"))
            for node in section.select(".ingre_list_name")
            if (name := _text(node))
        ]
    return None


def _comparison_title(value: str) -> str:
    """Normalize only comparison text; source values remain unchanged."""
    return " ".join(unicodedata.normalize("NFC", html_module.unescape(value)).split())


def parse_recipe(html: str, *, source_url: str) -> dict:
    """Extract DOM recipe content and supplement metadata from local HTML.

    Title mismatches are mechanical diagnostics. No ingredient/step comparison,
    quantity completion, semantic deduplication, or source rewriting occurs.
    """
    source_id, _ = _recipe_identity(source_url)
    soup = BeautifulSoup(html, "html.parser")
    summary = soup.select_one(".view2_summary")
    area = soup.select_one("#divConfirmedMaterialArea")
    if summary is None or area is None or soup.select_one(".view_step") is None:
        raise ParseError("Missing recipe summary, ingredient, or step structure")
    title = _text(summary.select_one("h3"))
    if title is None:
        raise ParseError("Missing DOM recipe title")
    metadata = _metadata(soup)
    findings = []
    if not metadata:
        findings.append(dict(code="jsonld_unavailable"))
    ld_title = _string(metadata.get("name"))
    if ld_title and _comparison_title(title) != _comparison_title(ld_title):
        findings.append(
            dict(
                code="source_mismatch",
                field="title",
                status="review_pending",
                observations=[
                    dict(representation=kind, value=value, source_url=source_url)
                    for kind, value in (("dom", title), ("jsonld", ld_title))
                ],
            )
        )
    author = metadata.get("author")
    if isinstance(author, dict):
        author = author.get("name")
    ingredients = _ingredients(area, findings)
    steps = _steps(soup, source_url)
    # Preserve incomplete source content, but make every absence reviewable.
    if not ingredients:
        findings.append(dict(code="missing_ingredients", field="ingredients"))
    for row in ingredients:
        if row["name_raw"] is None:
            findings.append(
                dict(code="missing_ingredient_name", field="ingredients", order=row["order"])
            )
    if not steps:
        findings.append(dict(code="missing_steps", field="steps"))
    for step in steps:
        if step["instruction"] is None:
            findings.append(dict(code="missing_instruction", field="steps", order=step["order"]))
    return dict(
        source=dict(
            namespace="10000recipe",
            id=source_id,
            url=source_url,
            author=_string(author),
            source_dates={
                key: metadata[key]
                for key in ("datePublished", "dateModified", "dateCreated")
                if _string(metadata.get(key))
            },
        ),
        title=title,
        description=_text(summary.select_one(".view2_summary_in"))
        or _string(metadata.get("description")),
        servings_text=_text(summary.select_one(".view2_summary_info1")),
        cooking_time_text=_text(summary.select_one(".view2_summary_info2")),
        difficulty_text=_text(summary.select_one(".view2_summary_info3")),
        ingredients=ingredients,
        steps=steps,
        listed_tools=_listed_tools(soup, source_url),
        findings=findings,
    )
