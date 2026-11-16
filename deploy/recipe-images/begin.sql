-- AI-generated manual image migration SQL with Codex, 2026-11-16; reviewed by Soohyun AN
\set ON_ERROR_STOP on
BEGIN;
SET LOCAL search_path = pg_catalog, public;
SET LOCAL standard_conforming_strings = on;
SET LOCAL lock_timeout = '15s';
SET LOCAL statement_timeout = '60s';
SELECT pg_advisory_xact_lock(151503);
-- Keep the checked catalog stable until verification and commit complete.
LOCK TABLE public.recipe, public.ingredient, public.recipe_step,
    public.recipe_ingredient, public.cooking_tool, public.allergen,
    public.recipe_cooking_tool, public.ingredient_allergen
    IN SHARE ROW EXCLUSIVE MODE;
CREATE TEMP TABLE image_previous (
    recipe_id integer PRIMARY KEY,
    main_image_url text
) ON COMMIT DROP;
