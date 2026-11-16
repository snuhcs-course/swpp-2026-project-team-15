-- AI-generated catalog preservation checks with Codex, 2026-11-16; reviewed by Soohyun AN
-- expected.sql supplies image_baseline(table_name, rows) and image_urls.
DO $$
DECLARE
    baseline record;
    actual jsonb;
    expected jsonb;
    image_column record;
BEGIN
    IF (SELECT count(*) FROM image_baseline) <> 8 OR
       EXISTS (SELECT 1 FROM image_baseline WHERE table_name NOT IN (
           'recipe', 'ingredient', 'recipe_step', 'recipe_ingredient',
           'cooking_tool', 'allergen', 'recipe_cooking_tool', 'ingredient_allergen'
       )) THEN
        RAISE EXCEPTION 'Expected baseline must contain exactly the eight catalog tables';
    END IF;
    FOR baseline IN SELECT * FROM image_baseline LOOP
        EXECUTE format(
            'SELECT COALESCE(jsonb_agg(doc ORDER BY doc), ''[]''::jsonb) FROM '
            '(SELECT to_jsonb(t) %s AS doc FROM public.%I t) records',
            CASE WHEN baseline.table_name = 'recipe' THEN '- ''main_image_url''' ELSE '' END,
            baseline.table_name
        ) INTO actual;
        SELECT COALESCE(jsonb_agg(doc ORDER BY doc), '[]'::jsonb)
            INTO expected FROM jsonb_array_elements(baseline.rows) doc;
        IF actual IS DISTINCT FROM expected THEN
            RAISE EXCEPTION 'Catalog baseline differs: %', baseline.table_name;
        END IF;
    END LOOP;
    IF (SELECT count(*) FROM image_urls) <> 537 OR
       (SELECT count(*) FROM image_urls WHERE main_image_url IS NOT NULL) <> 430 OR
       (SELECT count(DISTINCT main_image_url) FROM image_urls) <> 307 OR
       EXISTS (SELECT 1 FROM image_urls WHERE main_image_url IS NOT NULL AND
           main_image_url !~ '^/recipe-images/[A-Za-z0-9_.-]+\.(jpg|png)$') OR
       EXISTS (SELECT recipe_id FROM public.recipe EXCEPT SELECT recipe_id FROM image_urls) OR
       EXISTS (SELECT recipe_id FROM image_urls EXCEPT SELECT recipe_id FROM public.recipe) OR
       EXISTS (SELECT recipe_id FROM image_urls EXCEPT SELECT recipe_id FROM image_previous) OR
       EXISTS (SELECT recipe_id FROM image_previous EXCEPT SELECT recipe_id FROM image_urls) THEN
        RAISE EXCEPTION 'Mapping or previous URL snapshot is incomplete or out of scope';
    END IF;
    SELECT * INTO image_column FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'recipe'
          AND column_name = 'main_image_url';
    IF FOUND AND (image_column.is_nullable <> 'YES' OR
        image_column.data_type NOT IN ('text', 'character varying') OR
        image_column.column_default IS NOT NULL OR image_column.is_generated <> 'NEVER' OR
        (image_column.character_maximum_length IS NOT NULL AND
         image_column.character_maximum_length < (
             SELECT max(length(main_image_url)) FROM image_urls
         ))) THEN
        RAISE EXCEPTION 'Existing image column is incompatible';
    END IF;
END $$;
