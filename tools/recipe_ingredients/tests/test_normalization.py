# AI-generated normalization acceptance tests with Codex, 2026-11-15; reviewed by Soohyun An
"""Verify reviewed transformations without inventing recipe or quantity rules."""

import copy
import csv
import json

import pytest


def inputs(tmp_path):
    """Create approved split, exclusion, alias and repeated-row examples."""
    existing = {
        70: "김치",
        71: "김칫국물",
        451: "청고추",
        547: "홍고추",
        212: "미원",
        217: "바지락",
        219: "바질페스토",
        349: "어묵",
    }
    catalog = tmp_path / "Ingredient.csv"
    with catalog.open("w", encoding="utf-8", newline="") as handle:
        csv.writer(handle).writerows([("ingredient_id", "name"), *existing.items()])
    rules = []
    for raw, ids in [("김치+김치국물", [70, 71]), ("청홍고추", [451, 547])]:
        rules.append(
            dict(
                name_raw=raw,
                decision="split_existing",
                reason="Approved split",
                targets=[
                    dict(ingredient_id=str(i), normalized_name=existing[i], quantity_text=None)
                    for i in ids
                ],
            )
        )
    rules.extend(
        [
            dict(
                name_raw="전자렌지",
                decision="exclude_non_ingredient",
                reason="Tool",
                tool_candidate=dict(normalized_name="전자레인지", step_order=2),
            ),
            dict(
                name_raw="참치쌈장",
                decision="exclude_prepared_component",
                reason="Made in recipe",
                preparation_evidence=dict(steps=[1, 2, 3]),
            ),
        ]
    )
    for raw, name in [
        ("소고기다시다", "소고기다시다"),
        ("소고기 다시다", "소고기다시다"),
        ("연두", "연두"),
    ]:
        rules.append(
            dict(
                name_raw=raw,
                decision="new_requested",
                normalized_name=name,
                original_usage_note="Revision stays deferred",
            )
        )
    for raw, i in [("미원", 212), ("바지락 1봉", 217), ("바질페스트소스", 219), ("사각어묵", 349)]:
        rules.append(
            dict(
                name_raw=raw,
                decision="reuse_existing",
                ingredient_id=str(i),
                normalized_name=existing[i],
            )
        )
    rows = [
        dict(
            group="재료",
            order=i,
            name_raw=r["name_raw"],
            quantity_text=None,
            note_raw="Original note",
            source_material_id="99999",
        )
        for i, r in enumerate(rules, 1)
    ]
    rows[0]["quantity_text"] = "1국그릇"
    rows[-3]["quantity_text"] = "200g"
    repeated = copy.deepcopy(rows[-1])
    repeated.update(group="양념", quantity_text="1장", extra="Preserve unknown fields")
    rows.append(repeated)
    rows[-2].pop("quantity_text")
    selected = dict(
        source_run_id="fixture",
        extra="Unchanged",
        recipes=[
            dict(
                source_id="6910254",
                thumbnail_path="images/1.jpg",
                original_title="Original",
                recipe=dict(
                    source=dict(id="6910254", url="https://example.test/6910254"),
                    title="상추비빔밥",
                    description="Description",
                    listed_tools=["Bowl"],
                    ingredients=rows,
                    steps=[
                        dict(
                            order=1,
                            instruction="Make the sauce",
                            tips=["Keep tip"],
                            image_urls=["step.jpg"],
                        )
                    ],
                ),
            )
        ],
    )
    selected_path, decisions_path = tmp_path / "selected.json", tmp_path / "decisions.json"
    selected_path.write_text(json.dumps(selected, ensure_ascii=False), encoding="utf-8")
    decisions_path.write_text(json.dumps(dict(decisions=rules)), encoding="utf-8")
    return selected_path, decisions_path, catalog, selected


def generate(tmp_path):
    """Call the public entry point and ensure all supplied inputs remain unchanged."""
    from recipe_ingredients.normalization import build_documents

    selected_path, decisions_path, catalog, selected = inputs(tmp_path)
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    documents = build_documents(selected_path, decisions_path, catalog)
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir()} == before
    return documents, selected


def test_splits_keep_combined_amount_once_and_preserve_all_source_rows(tmp_path):
    docs, selected = generate(tmp_path)
    normalized = docs["normalized-recipes.json"]
    rows = normalized["recipes"][0]["recipe"]["ingredients"]
    sources = normalized["source_occurrences"]
    for raw, ids in [("김치+김치국물", [70, 71]), ("청홍고추", [451, 547])]:
        components = [r for r in rows if r["name_raw"] == raw]
        assert [r["ingredient_id"] for r in components] == ids
        assert [r["component_index"] for r in components] == [1, 2]
        assert all(r["quantity_text"] is None for r in components)
        assert components[0]["source"] == components[1]["source"]
    assert [s["original"] for s in sources] == selected["recipes"][0]["recipe"]["ingredients"]
    assert sum(s["original"].get("quantity_text") == "1국그릇" for s in sources) == 1
    assert docs["validation-report.json"]["split_components_without_quantity"] == 4


def test_exclusions_keep_evidence_and_never_rewrite_recipe_metadata(tmp_path):
    docs, selected = generate(tmp_path)
    actual = copy.deepcopy(docs["normalized-recipes.json"])
    report = docs["validation-report.json"]
    excluded = report["excluded_occurrences"]
    assert [e["original"]["name_raw"] for e in excluded] == ["전자렌지", "참치쌈장"]
    assert excluded[0]["review"]["tool_candidate"]["normalized_name"] == "전자레인지"
    assert excluded[1]["review"]["preparation_evidence"]["steps"] == [1, 2, 3]
    assert all(e["review"]["reason"] for e in excluded)
    actual.pop("source_occurrences")
    actual["recipes"][0]["recipe"]["ingredients"] = selected["recipes"][0]["recipe"]["ingredients"]
    assert actual == selected
    assert report["service_suitability_assessed"] is False
    assert report["catalog_published"] is False


def test_latest_aliases_repeated_rows_and_missing_amounts(tmp_path):
    docs, _ = generate(tmp_path)
    rows = docs["normalized-recipes.json"]["recipes"][0]["recipe"]["ingredients"]
    by_raw = {r["name_raw"]: r for r in rows}
    assert by_raw["소고기다시다"]["ingredient_id"] == by_raw["소고기 다시다"]["ingredient_id"]
    assert len({by_raw[n]["ingredient_id"] for n in ["소고기다시다", "연두", "미원"]}) == 3
    for raw, i in [("바지락 1봉", 217), ("바질페스트소스", 219), ("사각어묵", 349)]:
        assert by_raw[raw]["ingredient_id"] == i
    repeated = [r for r in rows if r["ingredient_id"] == 349]
    assert len(repeated) == 2
    assert "quantity_text" not in repeated[0]
    assert repeated[1]["quantity_text"] == "1장"
    assert by_raw["바지락 1봉"]["quantity_text"] == "200g"
    assert all(r["source_material_id"] == "99999" for r in rows)
    report = docs["validation-report.json"]
    assert report["source_rows"] == 12
    assert report["retained_source_rows"] == 8
    assert report["split_source_rows"] == report["excluded_source_rows"] == 2
    assert report["output_rows"] == 12
    assert len(report["missing_source_quantities"]) == 9
    assert report["validation_passed"] is True


def test_documents_roundtrip_and_invalid_inputs_produce_no_output(tmp_path):
    docs, _ = generate(tmp_path)
    assert set(docs) == {
        "ingredient-mapping.json",
        "normalized-recipes.json",
        "validation-report.json",
    }
    output = tmp_path / "synthetic-output"
    output.mkdir()
    for name, content in docs.items():
        path = output / name
        path.write_text(json.dumps(content, ensure_ascii=False), encoding="utf-8")
        assert json.loads(path.read_text(encoding="utf-8")) == content
    mapping = docs["ingredient-mapping.json"]
    assert mapping["input_hashes"] == docs["validation-report.json"]["input_hashes"]
    assert all("review" in row for row in mapping["mappings"])
    from recipe_ingredients.normalization import build_documents

    selected_path, decisions_path, catalog = [
        tmp_path / n for n in ["selected.json", "decisions.json", "Ingredient.csv"]
    ]
    decisions_path.write_text('{"decisions": []}', encoding="utf-8")
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir() if p.is_file()}
    with pytest.raises(ValueError, match="Missing decision"):
        build_documents(selected_path, decisions_path, catalog)
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir() if p.is_file()} == before
