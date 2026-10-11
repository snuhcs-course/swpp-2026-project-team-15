# AI-generated with Claude Code (Opus 5.5), 2026-10-11; review pending by Jaehyuk Choi.
from app.recipes.constants import STAPLE_SEASONINGS
from tests.conftest import StubVision


def test_recommend_returns_ranked_recipes_and_assumed_staples(make_client):
    response = make_client(StubVision()).post(
        "/recipes/recommend", json={"ingredients": ["김치", "두부", "밥", "계란", "대파"]}
    )

    body = response.json()
    assert response.status_code == 200
    assert body["staples_assumed"] == list(STAPLE_SEASONINGS)
    assert [(r["name"], r["missing"]) for r in body["recipes"]] == [
        ("계란볶음밥", []),
        ("김치찌개", ["돼지고기"]),
    ]


def test_recommend_validates_bounds(make_client):
    response = make_client(StubVision()).post(
        "/recipes/recommend", json={"ingredients": [], "max_missing": 6}
    )

    assert response.status_code == 422
