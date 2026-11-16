-- AI-generated manual URL recovery with Codex, 2026-11-16; reviewed by Soohyun AN
-- begin.sql, expected.sql, previous URL input, check.sql and verify.sql precede this.
-- Require the approved deployed values before replacing them with the saved snapshot.
UPDATE public.recipe r SET main_image_url = p.main_image_url
    FROM image_previous p WHERE r.recipe_id = p.recipe_id
    AND r.main_image_url IS DISTINCT FROM p.main_image_url;
-- Keep the compatible nullable column; never restore unrelated database contents.
