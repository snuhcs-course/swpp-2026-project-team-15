CREATE TABLE recipe (
    recipe_id INTEGER PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    cuisine_type VARCHAR(50),
    category VARCHAR(50),
    cooking_time VARCHAR(20),
    calories VARCHAR(20),
    servings VARCHAR(20),
    difficulty VARCHAR(50),
    main_image_url VARCHAR(2048),
    source_url VARCHAR(2048)
);

CREATE TABLE recipe_step (
    step_id INTEGER PRIMARY KEY,
    recipe_id INTEGER NOT NULL REFERENCES recipe(recipe_id),
    step_number INTEGER NOT NULL,
    instruction TEXT NOT NULL,
    image_url VARCHAR(2048),
    tip TEXT
);

CREATE TABLE ingredient (
    ingredient_id INTEGER PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE
);

CREATE TABLE recipe_ingredient (
    recipe_ingredient_id INTEGER PRIMARY KEY,
    recipe_id INTEGER NOT NULL REFERENCES recipe(recipe_id),
    ingredient_id INTEGER NOT NULL REFERENCES ingredient(ingredient_id),
    quantity_text VARCHAR(100),
    ingredient_type_code VARCHAR(7) NOT NULL,
    ingredient_type VARCHAR(50),
    original_name VARCHAR(255)
);

CREATE TABLE cooking_tool (
    tool_id INTEGER PRIMARY KEY,
    name VARCHAR(100) NOT NULL
);

CREATE TABLE recipe_cooking_tool (
    recipe_id INTEGER NOT NULL REFERENCES recipe(recipe_id),
    tool_id INTEGER NOT NULL REFERENCES cooking_tool(tool_id),
    PRIMARY KEY (recipe_id, tool_id)
);

CREATE TABLE allergen (
    allergen_id INTEGER PRIMARY KEY,
    name VARCHAR(100) NOT NULL
);

CREATE TABLE ingredient_allergen (
    ingredient_id INTEGER NOT NULL REFERENCES ingredient(ingredient_id),
    allergen_id INTEGER NOT NULL REFERENCES allergen(allergen_id),
    PRIMARY KEY (ingredient_id, allergen_id)
);
