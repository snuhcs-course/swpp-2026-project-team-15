# AI-generated with Claude Code (Sonnet 5.5), 2026-11-04; reviewed by Jaehyuk Choi.
"""Map a free-text ingredient name to a recipe-table ingredient.

Order: exact table name, then the synonym groups of the server
(`app.recipes.constants.with_synonyms`), then, only if an embedding function is given, the
nearest table name when its cosine similarity is at least `tau` and it leads the runner-up by at
least `margin`. Everything else stays unmapped, which is the safe default.

The embedding function is injected (`embed(texts) -> list of vectors`) so tests need no model;
`fastembed_embedder` loads one lazily:

    uv run --with fastembed python -m experiments.name_mapping.run_experiment --help
"""

from __future__ import annotations

import math
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

from app.recipes.constants import with_synonyms

Embed = Callable[[Sequence[str]], Sequence[Sequence[float]]]


@dataclass(frozen=True)
class Resolution:
    query: str
    ingredient_id: int | None
    name: str | None
    kind: str  # "exact", "synonym", "embedding" or "unmapped"
    score: float | None = None
    margin: float | None = None


def cosine(a: Sequence[float], b: Sequence[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


class Resolver:
    """Resolve names against `catalog` (ingredient id -> table name)."""

    def __init__(
        self,
        catalog: Mapping[int, str],
        embed: Embed | None = None,
        tau: float = 0.99,
        margin: float = 0.10,
    ) -> None:
        self.catalog = dict(catalog)
        self._ids = {name: i for i, name in sorted(self.catalog.items(), reverse=True)}
        self._embed = embed
        self.tau, self.margin = tau, margin
        self._names = [self.catalog[i] for i in sorted(self.catalog)]
        self._vectors = list(embed(self._names)) if embed else []

    def resolve(self, query: str) -> Resolution:
        q = query.strip()
        if q in self._ids:
            return Resolution(query, self._ids[q], q, "exact")
        for name in sorted(with_synonyms([q]) - {q}):
            if name in self._ids:
                return Resolution(query, self._ids[name], name, "synonym")
        if self._embed and q:
            return self._by_embedding(query, q)
        return Resolution(query, None, None, "unmapped")

    def _by_embedding(self, query: str, q: str) -> Resolution:
        vec = self._embed([q])[0]
        ranked = sorted(
            ((cosine(vec, v), n) for n, v in zip(self._names, self._vectors, strict=True)),
            key=lambda t: (-t[0], t[1]),
        )
        top, runner = ranked[0], ranked[1] if len(ranked) > 1 else (0.0, "")
        gap = top[0] - runner[0]
        if top[0] >= self.tau and gap >= self.margin:
            return Resolution(query, self._ids[top[1]], top[1], "embedding", top[0], gap)
        return Resolution(query, None, None, "unmapped", top[0], gap)


def fastembed_embedder(
    model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
) -> Embed:
    """Embedding function backed by fastembed (optional dependency, downloads the model once)."""
    from fastembed import TextEmbedding

    engine = TextEmbedding(model_name=model)
    return lambda texts: [list(map(float, v)) for v in engine.embed(list(texts))]


# --- Suggestion lists for typed input (what the app shows while the user types) ---------------


def suggest_app_rule(query: str, names: Sequence[str], limit: int = 5) -> list[str]:
    """The app's rule: names containing the input, prefix matches first, then shorter, then A-Z."""
    q = query.strip().lower()
    if not q:
        return []
    hits = [n for n in names if q in n.lower() and n.lower() != q]
    return sorted(hits, key=lambda n: (not n.lower().startswith(q), len(n), n))[:limit]


def suggest_with_aliases(
    query: str, names: Sequence[str], aliases: Mapping[str, str], limit: int = 5
) -> list[str]:
    """App rule, extended with wording variants (alias -> table name) seen in recipe sources."""
    out = suggest_app_rule(query, names, limit)
    q = query.strip().lower()
    for alias, name in sorted(aliases.items()):
        if q and q in alias.lower() and name not in out:
            out.append(name)
    return out[:limit]


_QUANTITY_TAIL = re.compile(
    r"\s*\d+(\.\d+)?\s*(kg|g|ml|l|개|단|봉지|팩|큰술|작은술|컵)?\s*$", re.IGNORECASE
)


def strip_wording(query: str) -> str:
    """Drop a quantity tail, a leading "다진 " and inner spaces.

    This pattern list mirrors how the synthetic typed inputs were built, so its high hit rate on
    them is circular; use it as a baseline only, and measure it on real typed input.
    """
    q = _QUANTITY_TAIL.sub("", query.strip())
    q = re.sub(r"^다진\s*", "", q)
    return q.replace(" ", "")
