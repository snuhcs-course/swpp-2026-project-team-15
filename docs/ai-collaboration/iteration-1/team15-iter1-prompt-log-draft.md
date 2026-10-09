# Iteration 1 Prompt Log — Contributor Wording

The sections below preserve the contributors' supplied prompt wording. The date on Jaehyuk's prompt was confirmed by him to the PM.

## Soohyun An

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

## Ahyoon Choi

## 2. Prompt History

[Ahyoon, 10-4] "안드로이드 스튜디오로 작동하는 클라 앱 프로그램 프론트엔드 작업 할 거야. 피그마로 UI 작업은 끝났어. 일단 하나의 화면을 안드로이드 스튜디오에서 어떻게 정의하는지 알려줘."

[Ahyoon, 10-4] "일단 온보딩 스크린 먼저 구현해보자. 뒤로 가기 버튼, 다음 버튼, 건너뛰기 버튼, 프로그레스 바, 실질적 내용으로 구성돼. 실질적 내용은 타이틀 텍스트, 서브 텍스트, 그리고 입력칸이나 선택 창 등... 으로 되어 있음." (줄바꿈 생략)

[Ahyoon, 10-4] "이제 fridge 탭 쪽을 구현하려고 하는데, 뭐부터 하면 될지 알려줘" (Figma 스크린샷 첨부)

[Ahoon, 10-4] "이제 CaptureScreen, AnalyzeScreen, ManualAddScreen을 만들어보자."

[Ahyoon, 10-4] "카메라 X 적용해줘"

[Ahyoon, 10-4] "텍스트 중간의 특정 글자에만 색이 넣고 싶으면 어떻게 해" → "그냥 텍스트에 태그로 받아서 AppText가 파싱하는 방식이면 안되냐"

[Ahyoon, 10-4] "MainScreen 유지하고, detail 클릭하면 디테일 뷰로 넘어가게 하고 싶어" (`RecipeScreen.kt`, `RecipeDetailScreen.kt` 첨부)

## Hyeokjun Kweon

## 2. 실제 프롬프트 발췌

아래 인용은 문장 자체를 고치지 않은 발췌다. 대화 내 개별 전송 날짜는 별도로 확인되지 않아 임의의 날짜를 붙이지 않았다.

> 내 생각에 너랑 내가 좀 더 git 리포지토리에 문서나 위키같은 거를 좀 수정 보완하고 그 다음에 저런 문서를 작성해야 할 거 같음. 일단 팀원들간의 회의 기록 같은 것도 업로드를 좀 해야 하고, 그 외에도 좀 이후에 다른 PM도 관리하기 위해 세팅해둬야 할 거 같아서 이 부분부터 진행하고, 그 뒤에 문서들을 완성해보자

> 제안 부분 없애고, 미확정 부분은 여러 가지를 고려하고 있다, 이런 식으로 표현하면 될 거 같아.

> 다음 md 내용을 시각화해서 mermaid로 표현해줘

이 마지막 문장은 PM이 10월 9일 사용한 프롬프트 문구로 제공했다.

## Jaehyuk Choi

## 2. 실제 프롬프트 기록

재혁이 10월 2일 사용한 프롬프트 문구:

> P0부터 P4까지 파이프라인 비교를 코드를 통해 제작해보았는데, 이를 바탕으로 최종적으로 선택한 파이프라인들을 토대로 P5를 구성해줘.
