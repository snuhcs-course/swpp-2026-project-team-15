# AI-generated with Claude Code (Opus 5.5), 2026-10-11 to 2026-10-14; review pending by Jaehyuk Choi.
import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.database import read_only_sqlite_engine
from app.main import create_app
from app.recipes.service import RecipeRepository
from app.vision.exceptions import VisionError
from app.vision.schemas import DetectedItem

SCHEMA = Path(__file__).resolve().parents[1] / "db" / "schema.sql"

INGREDIENTS = {
    1: "밥",
    2: "계란",
    3: "대파",
    4: "간장",
    5: "소금",
    6: "김치",
    7: "돼지고기",
    8: "두부",
    9: "고춧가루",
    10: "물",
    11: "설탕",
    12: "참기름",
    13: "달걀",
}
RECIPES = {
    1: ("계란볶음밥", "10분", "1인분", [1, 2, 3, 4, 5]),
    2: ("김치찌개", "30분", "2인분", [6, 7, 8, 9, 10]),
    3: ("만능 양념장", "5분", None, [4, 11, 12]),
}


@pytest.fixture
def recipe_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "recipes.sqlite3"
    with sqlite3.connect(db_path) as connection:
        connection.executescript(SCHEMA.read_text(encoding="utf-8"))
        connection.executemany("INSERT INTO ingredient VALUES (?, ?)", INGREDIENTS.items())
        for recipe_id, (name, time, servings, ingredient_ids) in RECIPES.items():
            connection.execute(
                "INSERT INTO recipe (recipe_id, name, cooking_time, servings) VALUES (?, ?, ?, ?)",
                (recipe_id, name, time, servings),
            )
            connection.executemany(
                "INSERT INTO recipe_ingredient (recipe_id, ingredient_id, ingredient_type_code)"
                " VALUES (?, ?, '3060001')",
                [(recipe_id, ingredient_id) for ingredient_id in ingredient_ids],
            )
            connection.executemany(
                "INSERT INTO recipe_step (recipe_id, step_number, instruction) VALUES (?, ?, ?)",
                [(recipe_id, 2, f"{name} 2단계"), (recipe_id, 1, f"{name} 1단계")],
            )
    connection.close()
    return db_path


class StubVision:
    def __init__(
        self, items: list[DetectedItem] | None = None, error: VisionError | None = None
    ) -> None:
        self.items = items or []
        self.error = error

    def detect(self, image: bytes, mime_type: str) -> list[DetectedItem]:
        if self.error:
            raise self.error
        return self.items


@pytest.fixture
def repository(recipe_db: Path) -> Iterator[RecipeRepository]:
    engine = read_only_sqlite_engine(recipe_db)
    yield RecipeRepository(engine)
    engine.dispose()  # closes pooled SQLite connections


@pytest.fixture
def make_client(repository: RecipeRepository):
    def build(vision: StubVision) -> TestClient:
        return TestClient(create_app(vision, repository))

    return build
