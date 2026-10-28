"""Build a self-contained candidate review page; it never contacts the API."""
from __future__ import annotations

import html
from datetime import UTC, datetime
from pathlib import Path

from .models import Recipe
from .search import SEARCH_LANGUAGE, read_cache


def build_sheet(batch: int, recipes: list[Recipe], cache_dir: Path, output: Path) -> None:
    stamp = datetime.now(UTC).isoformat(timespec="seconds")
    sections: list[str] = []
    for recipe in recipes:
        hits = read_cache(cache_dir / f"{recipe.id}.json", recipe.query,
                          lang=SEARCH_LANGUAGE) or []
        cards = []
        for i, hit in enumerate(hits):
            ident = html.escape(str(hit.get("id", "")), quote=True)
            page = html.escape(str(hit.get("pageURL", "")), quote=True)
            thumb = html.escape(str(hit.get("webformatURL", "")), quote=True)
            cards.append(f'<article class="card"><img loading="lazy" width="220" src="{thumb}" alt="Pixabay candidate">'
                f'<label><input type="radio" name="r{recipe.id}" value="{ident}" data-recipe="{recipe.id}" data-user="{html.escape(str(hit.get("user", "")), quote=True)}" data-user-id="{html.escape(str(hit.get("user_id", "")), quote=True)}" data-page="{page}" data-tags="{html.escape(str(hit.get("tags", "")), quote=True)}"> Select</label>'
                f'<p>Pixabay ID: {ident}<br>Photographer: {html.escape(str(hit.get("user", "")))}<br>Tags: {html.escape(str(hit.get("tags", "")))}<br>Resolution: {hit.get("imageWidth", "")} × {hit.get("imageHeight", "")}</p>'
                f'<a href="{page}" target="_blank" rel="noopener">Open on Pixabay</a></article>')
        empty = '<p>No candidates found.</p>' if not cards else ""
        cards.append(f'<label class="skip"><input type="radio" name="r{recipe.id}" value="" data-recipe="{recipe.id}"> Select none</label>')
        sections.append(f'<section><h2>{recipe.id}. {html.escape(recipe.name_ko)} ({html.escape(recipe.query)})</h2>{empty}<div class="cards">{"".join(cards)}</div></section>')
    document = f'''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Recipe image review — batch {batch:02}</title><style>body{{font:16px system-ui;margin:2rem;background:#f7f7f7}}section{{padding:1rem;background:white;margin:1rem 0}}.cards{{display:flex;gap:1rem;overflow:auto}}.card{{min-width:240px;border:1px solid #ccc;padding:.7rem}}.card img{{object-fit:cover}}.bar{{position:sticky;bottom:0;background:#222;color:white;padding:1rem}}</style></head><body><h1>Batch {batch:02}</h1><p>Generated {stamp}. webformatURL expires after 24 hours. Review within 24 hours of generation time.</p><p>Images from <a href="https://pixabay.com">Pixabay</a></p>{''.join(sections)}<div class="bar"><span id="count">0 selected</span> <button id="export">Export CSV</button></div><script>
const key='recipe-images-batch-{batch:02}';
function restore(){{let saved={{}};try{{saved=JSON.parse(localStorage.getItem(key)||'{{}}')}}catch{{}};document.querySelectorAll('input[type=radio]').forEach(x=>{{if(saved[x.name]===x.value)x.checked=true}});update()}}
function update(){{const selected=[...document.querySelectorAll('input[type=radio]:checked')].filter(x=>x.value);document.getElementById('count').textContent=selected.length+' selected';const s={{}};document.querySelectorAll('input[type=radio]:checked').forEach(x=>s[x.name]=x.value);localStorage.setItem(key,JSON.stringify(s))}}
document.addEventListener('change',e=>{{if(e.target.matches('input[type=radio]'))update()}});document.getElementById('export').onclick=()=>{{const rows=[['recipe_id','pixabay_id','user','user_id','page_url','tags']];document.querySelectorAll('input[type=radio]:checked').forEach(x=>{{if(x.value)rows.push([x.dataset.recipe,x.value,x.dataset.user,x.dataset.userId,x.dataset.page,x.dataset.tags])}});const csv=rows.map(r=>r.map(v=>'"'+String(v||'').replaceAll('"','""')+'"').join(',')).join('\\r\\n');const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([csv],{{type:'text/csv;charset=utf-8'}}));a.download='selected_{batch:02}.csv';a.click();URL.revokeObjectURL(a.href)}};restore();</script></body></html>'''
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(document, encoding="utf-8")
