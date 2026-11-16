-- AI-generated URL-only migration with Codex, 2026-11-16; reviewed by Soohyun AN
-- Run begin.sql, approved expected.sql, previous URL input and check.sql first.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM public.recipe r JOIN image_previous p USING (recipe_id)
        WHERE (to_jsonb(r)->>'main_image_url') IS DISTINCT FROM p.main_image_url
    ) THEN
        RAISE EXCEPTION 'Previous URL snapshot differs; inspect before migration';
    END IF;
    IF EXISTS (
        SELECT 1 FROM image_previous p JOIN image_urls u USING (recipe_id)
        WHERE p.main_image_url IS NOT NULL AND
              p.main_image_url IS DISTINCT FROM u.main_image_url
    ) THEN
        RAISE EXCEPTION 'Existing URL conflicts with approved mapping';
    END IF;
END $$;
ALTER TABLE public.recipe ADD COLUMN IF NOT EXISTS main_image_url text;
UPDATE public.recipe r SET main_image_url = u.main_image_url
    FROM image_urls u WHERE r.recipe_id = u.recipe_id
    AND r.main_image_url IS DISTINCT FROM u.main_image_url;
-- Caller verifies both URL values and all non-image data before COMMIT.
