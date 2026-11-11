# AI-assisted with Codex, 2026-11-11; reviewed by Soohyun An
"""Task 2.2/2.3 contracts for source-preserving details, tips, and listed tools."""

import importlib
import json
import re
from pathlib import Path

import pytest

FIXTURE = Path(__file__).parent / "fixtures/stage2_detail.html"
SOURCE_URL = "https://www.10000recipe.com/recipe/900001"
LD_SCRIPT = r'<script type="application/ld\+json">.*?</script>'


def with_jsonld(html, value):
    """Replace only synthetic metadata, leaving the separately asserted DOM intact."""
    replacement = '<script type="application/ld+json">' + json.dumps(value) + "</script>"
    return re.sub(LD_SCRIPT, lambda _: replacement, html, count=1, flags=re.DOTALL)


@pytest.fixture
def detail_html():
    return FIXTURE.read_text(encoding="utf-8")


def load_parser():
    return importlib.import_module("crawlers.tenkrecipes.parsing")


def test_detail_preserves_identity_and_available_metadata(detail_html):
    parser = load_parser()
    record = parser.parse_recipe(detail_html, source_url=SOURCE_URL)
    assert record["source"]["namespace"] == "10000recipe"
    assert record["source"]["id"] == "900001"
    assert record["source"]["url"] == SOURCE_URL
    assert record["source"]["author"] == "합성 작성자"
    assert record["source"]["source_dates"]["datePublished"] == "2026-01-01T12:00:00+09:00"
    assert record["title"] == "감자 & 달걀밥"
    assert record["description"] == "합성 레시피 설명"
    assert record["servings_text"] == "2인분"
    assert record["cooking_time_text"] == "20분 이내"
    assert record["difficulty_text"] == "초급"


def test_ingredient_rows_keep_groups_quantities_notes_and_repeated_source_ids(detail_html):
    parser = load_parser()
    ingredients = parser.parse_recipe(detail_html, source_url=SOURCE_URL)["ingredients"]
    assert [row["order"] for row in ingredients] == [1, 2, 3, 4]
    assert [row["group"] for row in ingredients] == ["[재료]", "[재료]", "[재료]", "[양념]"]
    assert [row["name_raw"] for row in ingredients] == ["감자", "미역", "감자", "간장"]
    assert [row["quantity_text"] for row in ingredients] == ["1/2개", "1줌", "약간", None]
    assert [row["note_raw"] for row in ingredients] == ["껍질 제거", "20g", None, None]
    assert [row["source_material_id"] for row in ingredients] == ["111", "222", "111", None]
    assert all(
        "ingredient_id" not in row and "ingredient_type_code" not in row for row in ingredients
    )


def test_missing_quantity_is_flagged_without_dropping_or_filling_the_row(detail_html):
    parser = load_parser()
    record = parser.parse_recipe(detail_html, source_url=SOURCE_URL)
    assert record["ingredients"][-1]["name_raw"] == "간장"
    assert record["ingredients"][-1]["quantity_text"] is None
    assert any(finding["code"] == "missing_quantity" for finding in record["findings"])


def test_notes_are_not_substituted_for_quantity(detail_html):
    parser = load_parser()
    ingredients = parser.parse_recipe(detail_html, source_url=SOURCE_URL)["ingredients"]
    assert ingredients[1]["name_raw"] == "미역"
    assert ingredients[1]["quantity_text"] == "1줌"
    assert ingredients[1]["note_raw"] == "20g"


def test_steps_preserve_order_and_repeated_instructions(detail_html):
    parser = load_parser()
    steps = parser.parse_recipe(detail_html, source_url=SOURCE_URL)["steps"]
    assert [step["order"] for step in steps] == [1, 2, 3]
    assert [step["instruction"] for step in steps] == [
        "감자를 썬다.",
        "팬에서 볶는다.",
        "팬에서 볶는다.",
    ]


def test_dom_tip_is_retained_separately_even_when_jsonld_omits_it(detail_html):
    parser = load_parser()
    steps = parser.parse_recipe(detail_html, source_url=SOURCE_URL)["steps"]
    assert steps[0]["instruction"] == "감자를 썬다."
    assert steps[0]["tips"] == ["두께는 일정하게 유지한다."]
    assert steps[1]["tips"] == steps[2]["tips"] == []
    assert steps[0]["image_urls"] == ["https://www.10000recipe.com/images/synthetic-step1.jpg"]
    assert steps[1]["image_urls"] == []


def test_listed_tools_are_not_mixed_into_ingredients_or_inferred_from_reviews(detail_html):
    parser = load_parser()
    record = parser.parse_recipe(detail_html, source_url=SOURCE_URL)
    assert [tool["name_raw"] for tool in record["listed_tools"]] == ["프라이팬", "도마"]
    assert all(tool["evidence"] for tool in record["listed_tools"])
    assert len(record["ingredients"]) == 4
    assert len(record["steps"]) == 3
    assert "오븐" not in [tool["name_raw"] for tool in record["listed_tools"]]


def test_absent_tools_are_not_inferred_from_cooking_actions(detail_html):
    parser = load_parser()
    html = re.sub(r"<!-- TOOLS_START -->.*?<!-- TOOLS_END -->", "", detail_html, flags=re.DOTALL)
    record = parser.parse_recipe(html, source_url=SOURCE_URL)
    assert record["listed_tools"] is None
    assert "팬" in record["steps"][1]["instruction"]


def test_present_empty_tools_section_is_distinct_from_unlisted(detail_html):
    parser = load_parser()
    html = re.sub(
        r"<!-- TOOLS_START -->.*?<!-- TOOLS_END -->",
        '<div class="best_tit"><b>조리도구</b></div><div class="ready_ingre3"><ul></ul></div>',
        detail_html,
        flags=re.DOTALL,
    )
    assert parser.parse_recipe(html, source_url=SOURCE_URL)["listed_tools"] == []


@pytest.mark.parametrize("layout", ["object", "array", "graph", "multiple_scripts"])
def test_recipe_metadata_is_found_among_unrelated_jsonld(detail_html, layout):
    parser = load_parser()
    script = re.search(
        r'<script type="application/ld\+json">(.*?)</script>', detail_html, re.DOTALL
    )
    recipe = json.loads(script.group(1))
    unrelated = {"@type": "BreadcrumbList", "name": "Not a recipe"}
    values = {
        "object": recipe,
        "array": [unrelated, recipe],
        "graph": {"@graph": [unrelated, recipe]},
    }
    if layout == "multiple_scripts":
        html = with_jsonld(detail_html, unrelated).replace(
            "</head>",
            '<script type="application/ld+json">' + json.dumps(recipe) + "</script></head>",
        )
    else:
        html = with_jsonld(detail_html, values[layout])
    record = parser.parse_recipe(html, source_url=SOURCE_URL)
    assert record["source"]["author"] == "합성 작성자"
    assert record["source"]["source_dates"]["datePublished"] == recipe["datePublished"]
    assert len(record["ingredients"]) == 4


@pytest.mark.parametrize("replacement", ["", '<script type="application/ld+json">{broken</script>'])
def test_dom_remains_parseable_without_valid_jsonld(detail_html, replacement):
    parser = load_parser()
    html = re.sub(LD_SCRIPT, lambda _: replacement, detail_html, count=1, flags=re.DOTALL)
    record = parser.parse_recipe(html, source_url=SOURCE_URL)
    assert record["title"] == "감자 & 달걀밥"
    assert len(record["ingredients"]) == 4
    assert len(record["steps"]) == 3
    assert any(finding["code"] == "jsonld_unavailable" for finding in record["findings"])


def test_dom_jsonld_disagreement_preserves_both_values_and_traceable_origins(detail_html):
    parser = load_parser()
    script = re.search(
        r'<script type="application/ld\+json">(.*?)</script>', detail_html, re.DOTALL
    )
    recipe = json.loads(script.group(1))
    recipe["name"] = "다른 제목"
    recipe["recipeIngredient"] = ["감자 999개"]
    recipe["recipeInstructions"] = [{"@type": "HowToStep", "text": "다른 조리법"}]
    html = with_jsonld(detail_html, recipe)
    record = parser.parse_recipe(html, source_url=SOURCE_URL)
    assert record["title"] == "감자 & 달걀밥"
    assert record["ingredients"][0]["quantity_text"] == "1/2개"
    assert len(record["ingredients"]) == 4
    conflicts = {
        finding["field"]: finding
        for finding in record["findings"]
        if finding["code"] == "source_mismatch"
    }
    assert set(conflicts) == {"title"}
    conflict = conflicts["title"]
    assert conflict["status"] == "review_pending"
    observations = conflict["observations"]
    assert len(observations) == 2
    assert {item["representation"] for item in observations} == {"dom", "jsonld"}
    for observation in observations:
        assert observation["source_url"] == SOURCE_URL

    titles = {item["representation"]: item["value"] for item in conflicts["title"]["observations"]}
    assert titles == {"dom": "감자 & 달걀밥", "jsonld": "다른 제목"}
    assert record["steps"][0]["instruction"] == "감자를 썬다."


def test_mechanical_comparison_ignores_encoding_and_whitespace_but_preserves_dom(detail_html):
    parser = load_parser()
    html = detail_html.replace('"name": "감자 & 달걀밥"', '"name": "  감자 &amp;   달걀밥  "')
    record = parser.parse_recipe(html, source_url=SOURCE_URL)
    assert record["title"] == "감자 & 달걀밥"
    assert record["ingredients"][1]["quantity_text"] == "1줌"
    assert record["steps"][0]["tips"] == ["두께는 일정하게 유지한다."]
    assert not any(finding["code"] == "source_mismatch" for finding in record["findings"])


def test_jsonld_supplements_missing_description_but_does_not_override_dom(detail_html):
    parser = load_parser()
    html = detail_html.replace('"description": "합성 레시피 설명"', '"description": "보완 설명"')
    assert parser.parse_recipe(html, source_url=SOURCE_URL)["description"] == "합성 레시피 설명"
    html = html.replace('<div class="view2_summary_in">합성 레시피 설명</div>', "")
    record = parser.parse_recipe(html, source_url=SOURCE_URL)
    assert record["description"] == "보완 설명"
    assert record["source"]["author"] == "합성 작성자"


def test_optional_summary_values_are_not_invented(detail_html):
    parser = load_parser()
    html = re.sub(LD_SCRIPT, "", detail_html, count=1, flags=re.DOTALL)
    html = re.sub(r'<span class="view2_summary_info[123]">.*?</span>', "", html)
    record = parser.parse_recipe(html, source_url=SOURCE_URL)
    assert record["servings_text"] is None
    assert record["cooking_time_text"] is None
    assert record["difficulty_text"] is None


def test_different_ids_produce_separate_source_records_without_semantic_merging(detail_html):
    parser = load_parser()
    first = parser.parse_recipe(detail_html, source_url=SOURCE_URL)
    second = parser.parse_recipe(detail_html, source_url=SOURCE_URL.replace("900001", "900002"))
    assert first["source"]["id"] == "900001"
    assert second["source"]["id"] == "900002"
    assert first["ingredients"] == second["ingredients"]
    assert first["steps"] == second["steps"]


def test_unrelated_html_is_not_a_successful_recipe():
    parser = load_parser()
    with pytest.raises(parser.ParseError):
        parser.parse_recipe("<html><body>Service unavailable</body></html>", source_url=SOURCE_URL)
