# AI-generated with Claude Code (Opus 5.5), 2026-11-19; not yet reviewed.
"""References of revised recipes: served path (V0) against closed reference choices (V1), a re-ask
message naming the bad reference (V2) and both (V3). Fridge = each dish's key ingredients.

    uv run python ../research/experiments/e2e_followups/revise_refs.py --server-dir . \
        --recipes FILE --variants V0 V1 V2 V3 --out FILE --allow-network
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import sys
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

CONFIG = Path.home() / ".config" / "mylittlechef" / "openrouter.env"


def read_key() -> str:
    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not key and CONFIG.exists():
        for line in CONFIG.read_text(encoding="utf-8").splitlines():
            if line.startswith("OPENROUTER_API_KEY="):
                key = line.split("=", 1)[1].strip().strip("\"'")
    return key


def closed_refs(schema: dict, n_rows: int, n_steps: int) -> dict:
    """V1: the request's own row and step numbers as the only allowed reference values."""
    out = copy.deepcopy(schema)
    props = out["properties"]["changes"]["items"]["properties"]
    props["ingredient_refs"]["items"] = {"type": "integer", "enum": list(range(1, n_rows + 1))}
    props["step_refs"]["items"] = {"type": "integer", "enum": list(range(1, n_steps + 1))}
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--server-dir", required=True)
    ap.add_argument("--recipes", required=True)
    ap.add_argument("--variants", nargs="+", default=["V0", "V1", "V2", "V3"])
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--dishes", nargs="*", default=[])
    ap.add_argument("--out", required=True)
    ap.add_argument("--allow-network", action="store_true")
    args = ap.parse_args()
    if not args.allow_network:
        sys.exit("refusing to call the model without --allow-network")
    sys.path.insert(0, str(Path(args.server_dir).resolve()))
    import app.dishes.revision as revision  # noqa: E402
    import app.dishes.revision_check as rc  # noqa: E402
    from app.dishes.dependencies import build_dish_parts  # noqa: E402

    env = {"DISH_LLM_API_KEY": read_key(), "DISH_RECIPES": args.recipes}
    parts = build_dish_parts(env)
    reviser, catalog = parts.reviser, parts.service.catalog
    served_request, served_changes = revision.revise_request, rc._checked_changes

    def named_changes(raw, recipe):
        """V2: the same check, with a message that names the change, the number and the range."""
        n_ing, n_steps = len(recipe.ingredients), len(recipe.steps)
        for k, item in enumerate(raw if isinstance(raw, list) else [], 1):
            if not isinstance(item, dict):
                continue
            ing, stp = item.get("ingredient_refs"), item.get("step_refs")
            bad_i = [i for i in ing or [] if not isinstance(i, int) or not 1 <= i <= n_ing]
            bad_s = [i for i in stp or [] if not isinstance(i, int) or not 1 <= i <= n_steps]
            if bad_i or bad_s:
                raise rc.Violation(
                    "bad_reference",
                    f"change {k} ({str(item.get('reason', ''))[:40]}) has ingredient_refs {bad_i} "
                    f"and step_refs {bad_s} outside the source: ingredient rows are 1..{n_ing}, "
                    f"steps are 1..{n_steps}; an added owned ingredient has no source row, so its "
                    "ingredient_refs is empty",
                )
        return served_changes(raw, recipe)

    calls: list[dict] = []
    real_complete = reviser.llm.complete

    def recording_complete(system, user, name, schema, max_tokens=None):
        started = time.monotonic()
        data = real_complete(system, user, name, schema, max_tokens)
        calls.append({"seconds": round(time.monotonic() - started, 2), "answer": data})
        return data

    reviser.llm.complete = recording_complete
    recipes = json.loads(Path(args.recipes).read_text(encoding="utf-8"))["recipes"]
    dish_ids = [d.id for d in catalog.all() if d.id in recipes]
    if args.dishes:
        dish_ids = [d for d in dish_ids if d in args.dishes]
    if args.limit:
        dish_ids = dish_ids[: args.limit]
    rows = []
    for variant in args.variants:
        closed = variant in ("V1", "V3")
        named = variant in ("V2", "V3")

        def request(recipe, dish_name, status, owned, _closed=closed):
            req = served_request(recipe, dish_name, status, owned)
            if not _closed:
                return req
            schema = closed_refs(req.schema, len(recipe.ingredients), len(recipe.steps))
            return type(req)(req.system, req.user, req.name, schema, req.max_tokens)

        revision.revise_request = request
        rc._checked_changes = named_changes if named else served_changes
        for dish_id in dish_ids:
            dish = catalog.get(dish_id)
            calls.clear()
            started = time.monotonic()
            try:
                result = reviser.revise(dish_id, list(dish.key_ingredients))
                status = result.status if result else "none"
                code = result.error.code if result and result.error else None
                changes = [c.model_dump() for c in (result.changes or [])] if result else []
            except Exception as exc:  # noqa: BLE001 - record and go on
                status, code, changes = "error", type(exc).__name__, []
            n_rows = len(recipes[dish_id]["ingredients"])
            n_steps = len(recipes[dish_id]["steps"])
            first = calls[0]["answer"] if calls else {}

            def out_of_range(answer, n_rows=n_rows, n_steps=n_steps):
                for ch in answer.get("changes") or []:
                    if not isinstance(ch, dict):
                        continue
                    if any(
                        not isinstance(i, int) or not 1 <= i <= n_rows
                        for i in ch.get("ingredient_refs") or []
                    ):
                        return True
                    if any(
                        not isinstance(i, int) or not 1 <= i <= n_steps
                        for i in ch.get("step_refs") or []
                    ):
                        return True
                return False

            mirrored = sum(
                1
                for ch in changes
                if ch["ingredient_refs"] and ch["ingredient_refs"] == ch["step_refs"]
            )
            rows.append(
                {
                    "variant": variant,
                    "dish": dish_id,
                    "status": status,
                    "code": code,
                    "calls": len(calls),
                    "seconds": round(time.monotonic() - started, 2),
                    "first_out_of_range": out_of_range(first) if first else None,
                    "final_out_of_range": out_of_range(calls[-1]["answer"]) if calls else None,
                    "changes": len(changes),
                    "mirrored_changes": mirrored,
                }
            )
            print(variant, dish_id, status, code, len(calls), mirrored, flush=True)
    revision.revise_request, rc._checked_changes = served_request, served_changes
    summary = {}
    for variant in args.variants:
        mine = [r for r in rows if r["variant"] == variant]
        summary[variant] = {
            "recipes": len(mine),
            "status": dict(Counter(r["status"] for r in mine)),
            "failed_codes": dict(Counter(r["code"] for r in mine if r["code"])),
            "first_out_of_range": sum(bool(r["first_out_of_range"]) for r in mine),
            "final_out_of_range": sum(bool(r["final_out_of_range"]) for r in mine),
            "revised_with_mirrored_change": sum(
                1 for r in mine if r["status"] == "revised" and r["mirrored_changes"]
            ),
            "calls": sum(r["calls"] for r in mine),
            "median_seconds": sorted(r["seconds"] for r in mine)[len(mine) // 2] if mine else None,
        }
    data = Path(args.recipes).read_bytes()
    out = {
        "at": datetime.now(UTC).isoformat(timespec="seconds"),
        "recipes_sha256": hashlib.sha256(data).hexdigest(),
        "summary": summary,
        "rows": rows,
    }
    Path(args.out).write_text(
        json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
