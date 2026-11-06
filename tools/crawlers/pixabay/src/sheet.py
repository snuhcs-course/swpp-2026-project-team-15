# AI-generated initial implementation with Codex (GPT-6 Luna Medium),
# 2026-11-03; reviewed by Ahyoon Choi.
# Modified with Codex (GPT-6), 2026-11-06; reviewed by Ahyoon Choi.
# Changes: Remove unused enumeration and wrap generated HTML and JavaScript.

"""Build a self-contained candidate review page; it never contacts the API."""

from __future__ import annotations

import html
from datetime import UTC, datetime
from pathlib import Path

from models import Recipe
from search import SEARCH_LANGUAGE, read_cache


def build_sheet(batch: int, recipes: list[Recipe], cache_dir: Path, output: Path) -> None:
    stamp = datetime.now(UTC).isoformat(timespec="seconds")
    sections: list[str] = []
    for recipe in recipes:
        hits = read_cache(cache_dir / f"{recipe.id}.json", recipe.query, lang=SEARCH_LANGUAGE) or []
        cards: list[str] = []
        for hit in hits:
            ident = html.escape(str(hit.get("id", "")), quote=True)
            user = html.escape(str(hit.get("user", "")), quote=True)
            user_id = html.escape(str(hit.get("user_id", "")), quote=True)
            page = html.escape(str(hit.get("pageURL", "")), quote=True)
            image_url = html.escape(str(hit.get("webformatURL", "")), quote=True)
            tags = html.escape(str(hit.get("tags", "")), quote=True)
            thumb = image_url
            cards.append(
                '<article class="card">'
                f'<img loading="lazy" width="220" src="{thumb}" '
                'alt="Pixabay candidate">'
                '<label><input type="radio" '
                f'name="r{recipe.id}" value="{ident}" '
                f'data-recipe="{recipe.id}" data-user="{user}" '
                f'data-user-id="{user_id}" data-page="{page}" '
                f'data-image-url="{image_url}" data-tags="{tags}"> Select</label>'
                f"<p>Pixabay ID: {ident}<br>Photographer: {user}<br>"
                f"Tags: {tags}<br>Resolution: {hit.get('imageWidth', '')} "
                f"× {hit.get('imageHeight', '')}</p>"
                f'<a href="{page}" target="_blank" rel="noopener">'
                "Open on Pixabay</a></article>"
            )
        empty = "<p>No candidates found.</p>" if not cards else ""
        cards.append(
            '<label class="skip"><input type="radio" '
            f'name="r{recipe.id}" value="" data-recipe="{recipe.id}"> '
            "Select none</label>"
        )
        recipe_name = html.escape(recipe.name_ko)
        recipe_query = html.escape(recipe.query)
        sections.append(
            f"<section><h2>{recipe.id}. {recipe_name} ({recipe_query})</h2>"
            f'{empty}<div class="cards">{"".join(cards)}</div></section>'
        )

    script = "\n".join(
        [
            f"const key='recipe-images-batch-{batch:02}';",
            "function restore() {",
            "  let saved = {};",
            "  try { saved = JSON.parse(localStorage.getItem(key) || '{}'); } catch {}",
            "  document.querySelectorAll('input[type=radio]').forEach((item) => {",
            "    if (saved[item.name] === item.value) item.checked = true;",
            "  });",
            "  update();",
            "}",
            "function update() {",
            "  const selected = [...document.querySelectorAll('input[type=radio]:checked')]",
            "    .filter((item) => item.value);",
            "  document.getElementById('count').textContent = selected.length + ' selected';",
            "  const state = {};",
            "  document.querySelectorAll('input[type=radio]:checked').forEach((item) => {",
            "    state[item.name] = item.value;",
            "  });",
            "  localStorage.setItem(key, JSON.stringify(state));",
            "}",
            "document.addEventListener('change', (event) => {",
            "  if (event.target.matches('input[type=radio]')) update();",
            "});",
            "document.getElementById('export').onclick = () => {",
            "  const rows = [['recipe_id', 'pixabay_id', 'user', 'user_id',",
            "    'page_url', 'image_url', 'tags']];",
            "  document.querySelectorAll('input[type=radio]:checked').forEach((item) => {",
            "    if (item.value) rows.push([item.dataset.recipe, item.value,",
            "      item.dataset.user, item.dataset.userId, item.dataset.page,",
            "      item.dataset.imageUrl, item.dataset.tags]);",
            "  });",
            "  const csv = rows.map((row) => row.map((value) =>",
            "    '\"' + String(value || '').replaceAll('\"', '\"\"') + '\"'",
            "  ).join(',')).join('\\r\\n');",
            "  const link = document.createElement('a');",
            "  link.href = URL.createObjectURL(new Blob([csv],",
            "    {type: 'text/csv;charset=utf-8'}));",
            f"  link.download = 'selected_{batch:02}.csv';",
            "  link.click();",
            "  URL.revokeObjectURL(link.href);",
            "};",
            "restore();",
        ]
    )
    document = (
        '<!doctype html><html><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width">'
        f"<title>Recipe image review — batch {batch:02}</title>"
        "<style>"
        "body{font:16px system-ui;margin:2rem;background:#f7f7f7}"
        "section{padding:1rem;background:white;margin:1rem 0}"
        ".cards{display:flex;gap:1rem;overflow:auto}"
        ".card{min-width:240px;border:1px solid #ccc;padding:.7rem}"
        ".card img{object-fit:cover}"
        ".bar{position:sticky;bottom:0;background:#222;color:white;padding:1rem}"
        "</style></head><body>"
        f"<h1>Batch {batch:02}</h1>"
        f"<p>Generated {stamp}. webformatURL expires after 24 hours. "
        "Review within 24 hours of generation time.</p>"
        '<p>Images from <a href="https://pixabay.com">Pixabay</a></p>'
        f"{''.join(sections)}"
        '<div class="bar"><span id="count">0 selected</span> '
        '<button id="export">Export CSV</button></div><script>'
        f"{script}"
        "</script></body></html>"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(document, encoding="utf-8")
