# AI Collaboration Report: Iteration 1

Tools used: Codex (GPT-6.1 Sol Medium, High)

## 1. Where AI was used

- Recipe DB: ER schema design and review, CSV preprocessing, SQL schema generation(`server/db/schema.sql`), Python script for importing CSV data into SQL tables(`import_recipes_.py`), README refinement(`README.md`)

## 2. Prompt History

[Soohyun, 10-03] Convert a table in ER_diagram_csv_basis.md into an ER diagram.  
[Soohyun, 10-04] Generate CSV files based on raw CSV data and a ER diagram.  
[Soohyun, 10-04] Verify whether the column names of the schema match that of raw CSV files. Set the type appropriate for each column.  
[Soohyun, 10-05] Write a script that imports CSV files.  
[Soohyun, 10-06] Check the content of a new xlsx file.  
[Soohyun, 10-06] Check whether it is possible to use (`recipe_id`, `original_name`, `ingredient_type_code`) as a primary key of `RecipeIngredient`.  
[Soohyun, 10-06] Modify the schema. Convert this CSV data of ingredient information into SQL tables.  
[Soohyun, 10-06] What are names with brackets in ingredient data? Handle names with brackets.  
[Soohyun, 10-07] Write a draft for GitHub Wiki based on working history.  
[Soohyu, 10-09] Draw an ER diagram based on the current schema.

### 2-1. Full-log

[Soohyun, 10-03] ER_diagram_csv_basis.md 파일의 표를 바탕으로 ER diagram으로 전환해.

[Soohyun, 10-04] data/레시피+기본정보\_20260927.csv와 data/레시피+과정정보\_20261004.csv, ER_diagram_csv_basis.md를 바탕으로, ER model에 맞는 CSV 파일들을 생성해줘.  
Source entity는 만들지 않는다. required/optional ingredient도 만들지 않는다.
현재 재료 원본 파일은 아직 없으므로 Ingredient/RecipeIngredient는 스키마 템플릿만 만들거나 실제 데이터 부재를 명확히 처리한다.
핵심 구조는 Recipe, RecipeStep, Ingredient, RecipeIngredient(Recipe-Ingredient M:N 관계), CookingTool, RecipeCookingTool(Recipe-CookingTool M:N), Allergen, IngredientAllergen(Ingredient-Allergen M:N)이다.
Recipe에는 source_url을 둘 수 있다. RecipeStep에는 step_number, instruction, optional image_url, optional tip. CSV 원본의 공백 문자열은 NULL/빈값으로 정리하고, 기본정보에 존재하지 않는 recipe code의 step은 제외한다.
원본 CSV를 보존하고 별도의 출력 CSV들을 만들어라. 생성 전 spreadsheet skill 지침을 읽고 따른다. 각 CSV의 컬럼 매핑과 행 수, 아직 비어 있는 테이블/이유를 요약해서 사용자에게 전달한다.

[Soohyun, 10-04]
ER 다이어그램의 attribute 이름이 csv랑 잘 맞는지도 확인해봐. 최대한 일치하는 방향으로 (수정 최소화)
그리고 int, varchar, string 등 다양한 type이 있으니까, 최대한 잘 맞는 type으로 가는 게 좋을듯.

[Soohyun, 10-05]
server/db/ 아래 스크립트부터 작성해 봐야할듯. csv 입력을 받는 스크립트부터 작성해.

[Soohyun, 10-06]
레시피 재료 정보를 받았어. 내용을 먼저 확인해 봐. (data/레시피\_재료정보.xlsx)

[Soohyun, 10-06]
음.. 그럼 재료 타입 코드까지 활용해서 recipeingredient의 키로 쓰는 건?

[Soohyun, 10-06]
좋아. 그렇게 해서 스키마를 수정하고, 레시피 재료 정보 xlsx을 csv로 변환한 파일을 줄게. table로 생성할 수 있도록 하자.

[Soohyun, 10-06]
근데 ingredient.csv에서
1,[국물용 소금물] 소금
2,[멸치장국] 국멸치
3,[배합초] 소금
4,[불고기양념] 간장
5,[비빔양념] 간장
6,[쇠고기양념] 간장
7,[쇠고기양념] 다진파
8,[쇠고기육수] 쇠뼈
9,[양념장] 고춧가루
10,[양념장] 다진파
11,[육수] 시판용장국
12,[절임간장] 진간장
13,[절임용 소금물] 물
14,[절임용 소금물] 소금
15,[절임용소금물] 소금
16,[초고추장] 고추장
[ ]안에 있는 건 뭐야? 네가 넣은 거야?

[Soohyun, 10-06]
좋아. 수정해.

[Soohyun, 10-07]
좋아. 그 전에, 지금까지 커밋한 내역을 바탕으로 github wiki를 작성하려고 해. 내용을 정리해보자.

[Soohyun, 10-09]
현재 설계에 맞게 ER 다이어그램을 그려.

## 3. What AI Did Well

- SQL and Python script generation: AI-generated SQL statements and a Python data import script executed successfully without manual code fixes.
- Schema refinement: Evaluated the compatibility of a new ingredient dataset wiht the existing schema and proposed modifications, including a candidate composite primary key for `RecipeIngredient`.

## 4. Hallucinations / Errors

- Incomplete ingredient name normalization: Preserved bracketed prefixes (e.g., [국물용 소금물] 소금) in `Ingredient.csv`, potentially cuasing identical ingredients to be treated as separate items. Caught during manual CSV inscpection. Fixed by normalizing ingredient names while preserving the original values in `RecipeIngredient.original_name`

## 5. Prompt Revisions

- No significant prompt revisions were made.

## 6. Manual Fixes and Why

- No manual code fixes were made in the AI-generated SQL schema or Python import script.
- Wrote the `Overview` section of the AI-generated Recipe Database Wiki draft manually because AI ommited the section entirely, since writing the short ection directly was faster than prompting AI and reviewing again.

## 7. Takeaway for Iteration 2

- For more complex tasks, use a specification-driven approach instead of relying solely on conversational prompts.
