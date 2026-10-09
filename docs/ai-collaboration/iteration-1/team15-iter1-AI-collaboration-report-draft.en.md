# AI Collaboration Report – Iteration 1 (2026-09-23 to 2026-10-09)

**Written by:** Hyeokjun Kweon (PM) · **Contributors:** Soohyun An, Ahyoon Choi, Jaehyuk Choi  
**Tools:** Codex (Soohyun: GPT-6.1 Sol; Hyeokjun and Jaehyuk: model versions unrecorded); Claude chat (Ahyoon: Sonnet 5.5).

## 1. Where AI was used

Soohyun used Codex for the recipe ER model, CSV preparation, [SQL schema](https://github.com/snuhcs-course/swpp-2026-project-team-15/blob/main/server/db/schema.sql#L1), and [CSV importer](https://github.com/snuhcs-course/swpp-2026-project-team-15/blob/main/server/db/import_recipes.py#L3). Claude supplied initial drafts of Ahyoon's Android navigation, onboarding, fridge, and ingredient-entry flow; she adapted them (for example, [AppNavHost](https://github.com/snuhcs-course/swpp-2026-project-team-15/blob/main/android/MyLittleChef/app/src/main/java/com/example/mylittlechef/navigation/AppNavHost.kt#L1) and [CaptureScreen](https://github.com/snuhcs-course/swpp-2026-project-team-15/blob/main/android/MyLittleChef/app/src/main/java/com/example/mylittlechef/ui/fridge/add/CaptureScreen.kt#L1)). Hyeokjun used Codex for PM handoff, TA presentation drafts, and Mermaid diagrams. Jaehyuk used Codex during P0–P5 research; the exact generated research-code lines remain unverified. The team decided task ownership, schedule additions, and completion scope without AI.

## 2. Prompt history

- Soohyun, 10-05: “server/db/ 아래 스크립트부터 작성해 봐야할듯. csv 입력을 받는 스크립트부터 작성해.”
- Soohyun, 10-06: “음.. 그럼 재료 타입 코드까지 활용해서 recipeingredient의 키로 쓰는 건?”
- Ahyoon, 10-04: “이제 CaptureScreen, AnalyzeScreen, ManualAddScreen을 만들어보자.”; “카메라 X 적용해줘”
- Hyeokjun, 10-09 (PM-supplied wording): “다음 md 내용을 시각화해서 mermaid로 표현해줘”
- Jaehyuk, 10-02: “P0부터 P4까지 파이프라인 비교를 코드를 통해 제작해보았는데, 이를 바탕으로 최종적으로 선택한 파이프라인들을 토대로 P5를 구성해줘.”

The [full Wiki prompt log](https://github.com/snuhcs-course/swpp-2026-project-team-15/wiki/AI-Collaboration-Report-Iteration-1-Prompt-Log) and [individual records](https://github.com/snuhcs-course/swpp-2026-project-team-15/tree/main/docs/ai-collaboration/iteration-1) preserve the context.

## 3. What AI did well

Soohyun reports that the generated schema and importer ran without manual code repairs; the local DB imports 537 recipes, 2,870 steps, and 5,933 recipe–ingredient rows. Ahyoon reports that Claude organized six Figma frames into four screens and reusable states, saving about three hours by her estimate. `EditableIngredientList` reduced duplicated UI. Codex made PM handoff and presentation drafts easier to review; no time saving was measured there.

## 4. Hallucinations and errors

AI left bracketed preparation prefixes such as `[불고기양념] 간장` in ingredient names. Soohyun caught duplicates through CSV inspection and separated canonical names from source labels. Ahyoon found an unsupported `rememberSaveable` `Set<String>` and a missing import in an onboarding draft. Dependency advice preceded a Kotlin metadata mismatch caught by Gradle. Exact repair times were not logged.

## 5. Prompt revisions

Ahyoon changed “텍스트 중간의 특정 글자에만 색이 넣고 싶으면 어떻게 해” to “그냥 텍스트에 태그로 받아서 AppText가 파싱하는 방식이면 안되냐”. The tag format removed ambiguity when a word repeated. Hyeokjun asked for undecided backend and inventory choices to be presented as options, so the TA slides no longer implied a final decision.

## 6. Manual fixes and why

Soohyun wrote the Wiki overview omitted by AI. Ahyoon redesigned the [AppText tag format](https://github.com/snuhcs-course/swpp-2026-project-team-15/blob/main/android/MyLittleChef/app/src/main/java/com/example/mylittlechef/ui/components/AppText.kt#L1), wrote recipe screens and ViewModels herself, and corrected Figma values. Hyeokjun checked final presentation wording and team decisions. Code comments now identify confirmed AI-generated initial drafts; research code has no line-level AI attribution because its authorship boundary is unverified. These reviews required project context and human judgment.

**Iteration 2 takeaway:** Keep source data, real-photo results, team decisions, and AI drafts traceable separately.
