# AI-assisted with Codex, 2026-11-11; reviewed by Soohyun An
# Test reorganization assisted by Codex, 2026-11-15; reviewed by Soohyun An
"""Offline list parsing contracts for task 2.1, using synthetic source structure."""

import importlib
from pathlib import Path

import pytest

FIXTURE = Path(__file__).parent / "fixtures/list.html"
SOURCE_URL = "https://www.10000recipe.com/recipe/list.html?cat2=18&cat4=52&order=reco&page=1"


@pytest.fixture
def list_html():
    return FIXTURE.read_text(encoding="utf-8")


def load_parser():
    """Import at execution time so absent implementation fails without breaking discovery."""
    return importlib.import_module("crawlers.tenkrecipes.parsing")


def test_list_preserves_filters_page_and_candidate_positions(list_html):
    parser = load_parser()
    page = parser.parse_list_page(list_html, source_url=SOURCE_URL)
    assert page["status"] == "ok"
    assert page["source_url"] == SOURCE_URL
    assert page["page"] == 1
    assert page["category_code"] == "52"
    assert [item["source_id"] for item in page["items"]] == ["900001", "900002"]
    assert [item["position"] for item in page["items"]] == [1, 2]
    assert [item["title"] for item in page["items"]] == ["감자 & 달걀밥", "감자 & 달걀밥"]


def test_list_uses_recipe_thumbnails_instead_of_badges_or_avatars(list_html):
    parser = load_parser()
    items = parser.parse_list_page(list_html, source_url=SOURCE_URL)["items"]
    assert [item["thumbnail_url"] for item in items] == [
        "https://recipe1.ezmember.co.kr/cache/recipe/synthetic-first_m.jpg",
        "https://www.10000recipe.com/images/synthetic-second_m.jpg",
    ]
    assert items[0]["source_url"] == "https://www.10000recipe.com/recipe/900001"
    assert items[1]["source_url"] == "https://www.10000recipe.com/recipe/900002"


def test_list_ignores_recipe_links_outside_candidate_cards(list_html):
    parser = load_parser()
    items = parser.parse_list_page(list_html, source_url=SOURCE_URL)["items"]
    assert len(items) == 2
    assert all(item["source_id"] != "999999" for item in items)


def test_list_retains_duplicate_id_observations_for_later_allocation(list_html):
    parser = load_parser()
    html = list_html.replace("/recipe/900002", "/recipe/900001")
    items = parser.parse_list_page(html, source_url=SOURCE_URL)["items"]
    assert [item["source_id"] for item in items] == ["900001", "900001"]
    assert [item["position"] for item in items] == [1, 2]


def test_list_page_number_comes_from_its_source_url(list_html):
    parser = load_parser()
    url = SOURCE_URL.replace("page=1", "page=2")
    page = parser.parse_list_page(list_html, source_url=url)
    assert page["page"] == 2
    assert page["source_url"] == url


def test_empty_list_is_distinct_from_a_changed_layout():
    parser = load_parser()
    html = """<html><body><input name="cat2" value="18"><input name="cat4" value="52">
    <input name="order" value="reco"><div>총 0개의 맛있는 레시피가 있습니다.</div>
    <ul class="common_sp_list_ul"></ul></body></html>"""
    page = parser.parse_list_page(html, source_url=SOURCE_URL)
    assert page["status"] == "empty"
    assert page["items"] == []


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ('name="cat2" value="18"', 'name="cat2" value="19"'),
        ('name="cat4" value="52"', 'name="cat4" value="63"'),
        ('name="order" value="reco"', 'name="order" value="date"'),
        ('<input name="cat2" value="18">', ""),
        ('class="common_sp_list_ul"', 'class="unknown_list"'),
        ('class="common_sp_list_li"', 'class="unknown_card"'),
    ],
)
def test_filter_loss_and_layout_changes_are_not_silent_empty_success(list_html, old, new):
    parser = load_parser()
    assert old in list_html
    with pytest.raises(parser.ParseError):
        parser.parse_list_page(list_html.replace(old, new), source_url=SOURCE_URL)


def test_non_recipe_page_is_a_structural_error():
    parser = load_parser()
    with pytest.raises(parser.ParseError):
        parser.parse_list_page(
            "<html><body>Service unavailable</body></html>", source_url=SOURCE_URL
        )
