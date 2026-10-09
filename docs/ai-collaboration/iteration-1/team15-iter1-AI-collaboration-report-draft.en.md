# AI Collaboration Report – Iteration 1 (2026-09-23 to 2026-10-09)

**Written by:** Hyeokjun Kweon (PM) · **Contributors:** Soohyun An, Ahyoon Choi, Jaehyuk Choi  
**Tools reported:** Codex (Soohyun: GPT-6.1 Sol; Hyeokjun and Jaehyuk: model version unrecorded); Claude chat (Ahyoon: Sonnet 5.5).

## 1. Where AI was used

Soohyun used Codex for the recipe ER model, entity CSV transformation, [`server/db/schema.sql`](https://github.com/snuhcs-course/swpp-2026-project-team-15/blob/0405ffc/server/db/schema.sql), [`import_recipes.py`](https://github.com/snuhcs-course/swpp-2026-project-team-15/blob/0405ffc/server/db/import_recipes.py), and Wiki text. Ahyoon used Claude to draft Android navigation, onboarding, digital-refrigerator, and capture/analysis/manual-add screens on [the Android branch](https://github.com/snuhcs-course/swpp-2026-project-team-15/tree/ae22ec7/android/MyLittleChef); she wrote recipe screens and ViewModels herself. Hyeokjun used Codex for [PM handoff documentation](https://github.com/snuhcs-course/swpp-2026-project-team-15/blob/main/docs/pm-handoff.md), TA presentation drafts, Mermaid diagrams, and submission-document wording. The PM reports that Jaehyuk used Codex for research and AI pipeline exploration, represented by [research code](https://github.com/snuhcs-course/swpp-2026-project-team-15/commit/4ea64e3) and [research Wiki pages](https://github.com/snuhcs-course/swpp-2026-project-team-15/wiki/Pipeline-Candidate-Comparative-Evaluation); those artifacts establish the work, not which lines Codex produced. Team members decided task ownership, new schedule tasks, and completion scope themselves.

## 2. Prompt history

Verbatim examples from the submitted individual records and PM prompts:

- Soohyun, 10-05: “server/db/ 아래 스크립트부터 작성해 봐야할듯. csv 입력을 받는 스크립트부터 작성해.”
- Soohyun, 10-06: “음.. 그럼 재료 타입 코드까지 활용해서 recipeingredient의 키로 쓰는 건?”
- Ahyoon, 10-04: “이제 CaptureScreen, AnalyzeScreen, ManualAddScreen을 만들어보자.”; “카메라 X 적용해줘”
- Hyeokjun, 10-09 (PM-supplied wording): “다음 md 내용을 시각화해서 mermaid로 표현해줘”
- Jaehyuk, 10-02: “P0부터 P4까지 파이프라인 비교를 코드를 통해 제작해보았는데, 이를 바탕으로 최종적으로 선택한 파이프라인들을 토대로 P5를 구성해줘.”

The [full prompt log](team15-iter1-prompt-log-draft.md) preserves supplied wording. The [Soohyun](iter1_AI_report_soohyun.md), [Ahyoon](iter1-AI-report-ahyoon.md), [Hyeokjun](iter1_AI_report_hyeokjun.md), and [Jaehyuk](iter1_AI_report_jaehyuk.md) records give context.

## 3. What AI did well

Soohyun reports that the generated SQL schema and CSV importer ran without manual code repairs. AI helped examine how the newly received ingredient file fit the schema; the local prototype now imports 537 recipes, 2,870 steps, and 5,933 recipe–ingredient rows. Ahyoon reports that Claude grouped six Figma frames into four screens and reusable states, saving roughly three hours by her estimate; `EditableIngredientList` reduced duplication. For PM work, AI organized handoff checks and presentation alternatives into reviewable drafts. No time-saving estimate was recorded for those tasks.

## 4. Hallucinations and errors

Soohyun found bracketed preparation prefixes such as `[불고기양념] 간장` in generated ingredient names. Manual CSV inspection exposed duplicate canonical ingredients; the team normalized `Ingredient.name` while retaining the original source label. Ahyoon found an unsupported `rememberSaveable` `Set<String>` and a missing import in an onboarding draft; dependency advice also preceded a Kotlin metadata mismatch, detected during Gradle build. Hyeokjun found that Codex had assigned all three document revision dates to October 9 by treating publication as creation. He supplied the private draft dates, and [the history was corrected](https://github.com/snuhcs-course/swpp-2026-project-team-15/commit/9eff8d1). Exact repair times for these errors were not logged.

## 5. Prompt revisions

Ahyoon changed “텍스트 중간의 특정 글자에만 색이 넣고 싶으면 어떻게 해” to “그냥 텍스트에 태그로 받아서 AppText가 파싱하는 방식이면 안되냐”. The latter specified a tag-based interface and avoided ambiguity when a highlighted word repeated. Hyeokjun asked for undecided backend and inventory choices to be presented as options rather than decisions; the presentation text then matched the team's open status.

## 6. Manual fixes and why

Soohyun manually wrote the Wiki overview omitted by AI. Ahyoon replaced the generated `AppText` tagging approach, wrote recipe screens and ViewModels herself, and corrected Figma colors and dimensions. Hyeokjun selected and edited final presentation wording, confirmed team decisions, and chose to capture rendered Mermaid diagrams manually for Word. These edits required project context, visual judgment, or direct team authority that the tools lacked. The team will attach code-level AI attribution markers after each code owner verifies the generated sections.

**Iteration 2 takeaway:** Keep source data, real-photo evaluation, human decisions, and AI-generated drafts traceable separately; provide exact schemas and existing files in prompts before asking for implementation.
