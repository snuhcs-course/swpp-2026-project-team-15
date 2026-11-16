-- AI-generated saved URL verification with Codex, 2026-11-16; reviewed by Soohyun AN
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM public.recipe r JOIN image_previous p USING (recipe_id)
        WHERE r.main_image_url IS DISTINCT FROM p.main_image_url
    ) THEN
        RAISE EXCEPTION 'Previous URL verification failed';
    END IF;
END $$;
