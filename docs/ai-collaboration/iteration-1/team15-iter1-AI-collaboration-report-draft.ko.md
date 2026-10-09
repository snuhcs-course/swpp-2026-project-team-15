# AI 협업 보고서 — Iteration 1 (2026-09-23~2026-10-09)

**작성:** 권혁준(PM) · **참여:** 안수현, 최아윤, 최재혁  
**도구:** Codex(수현: GPT-6.1 Sol; 혁준·재혁: 모델 버전 미기록), Claude 채팅(아윤: Sonnet 5.5).

## 1. AI를 사용한 곳

수현은 레시피 ER 모델, CSV 정리, [SQL 스키마](https://github.com/snuhcs-course/swpp-2026-project-team-15/blob/main/server/db/schema.sql#L1), [CSV 입력 스크립트](https://github.com/snuhcs-course/swpp-2026-project-team-15/blob/main/server/db/import_recipes.py#L3)에 Codex를 사용했다. 아윤은 Claude가 만든 Android 내비게이션·온보딩·냉장고·재료 입력 흐름의 초안을 가져와 수정했다([AppNavHost](https://github.com/snuhcs-course/swpp-2026-project-team-15/blob/main/android/MyLittleChef/app/src/main/java/com/example/mylittlechef/navigation/AppNavHost.kt#L1), [CaptureScreen](https://github.com/snuhcs-course/swpp-2026-project-team-15/blob/main/android/MyLittleChef/app/src/main/java/com/example/mylittlechef/ui/fridge/add/CaptureScreen.kt#L1)). 혁준은 PM 인수인계·TA 발표 초안·Mermaid 도표에 Codex를 사용했다. 재혁은 P0~P5 연구에 Codex를 사용했지만, 연구 코드에서 AI가 작성한 줄은 특정되지 않았다. 작업 담당자, 추가 일정표 Task, 완료 범위는 팀이 직접 결정했다.

## 2. 실제 프롬프트 기록

- 수현(10월 5일): “server/db/ 아래 스크립트부터 작성해 봐야할듯. csv 입력을 받는 스크립트부터 작성해.”
- 수현(10월 6일): “음.. 그럼 재료 타입 코드까지 활용해서 recipeingredient의 키로 쓰는 건?”
- 아윤(10월 4일): “이제 CaptureScreen, AnalyzeScreen, ManualAddScreen을 만들어보자.”; “카메라 X 적용해줘”
- 혁준(10월 9일, PM이 제공한 문구): “다음 md 내용을 시각화해서 mermaid로 표현해줘”
- 재혁(10월 2일): “P0부터 P4까지 파이프라인 비교를 코드를 통해 제작해보았는데, 이를 바탕으로 최종적으로 선택한 파이프라인들을 토대로 P5를 구성해줘.”

[Wiki 전체 프롬프트 로그](https://github.com/snuhcs-course/swpp-2026-project-team-15/wiki/AI-Collaboration-Report-Iteration-1-Prompt-Log)와 [개인별 기록](https://github.com/snuhcs-course/swpp-2026-project-team-15/tree/main/docs/ai-collaboration/iteration-1)에 맥락을 남겼다.

## 3. AI가 잘한 점

수현의 보고에 따르면 AI가 만든 스키마와 입력 스크립트는 수동 코드 수정 없이 실행됐고, 로컬 DB에 레시피 537개·조리 단계 2,870개·레시피 재료 관계 5,933개가 입력된다. 아윤의 추산으로 Claude는 Figma 프레임 6개를 화면 4개와 재사용 상태로 정리해 약 3시간을 절약했다. `EditableIngredientList`는 UI 중복을 줄였다. Codex는 PM 인수인계와 발표 초안 검토에 도움을 줬으나 절약 시간은 측정하지 않았다.

## 4. 오류·환각

AI가 `[불고기양념] 간장` 같은 조리 묶음 접두어를 재료 이름에 남겼다. 수현은 CSV 수동 검사에서 중복을 발견해 정규화 이름과 원본 표기를 분리했다. 아윤은 온보딩 초안의 지원되지 않는 `rememberSaveable` `Set<String>`과 누락된 import를 확인했다. 의존성 안내 후 생긴 Kotlin 메타데이터 불일치는 Gradle 빌드에서 발견했다. 정확한 수정 시간은 기록하지 않았다.

## 5. 수정한 프롬프트

아윤은 “텍스트 중간의 특정 글자에만 색이 넣고 싶으면 어떻게 해”를 “그냥 텍스트에 태그로 받아서 AppText가 파싱하는 방식이면 안되냐”로 바꿨다. 태그 방식으로 반복되는 단어의 위치 모호함을 줄였다. 혁준은 미정인 백엔드·재고 저장 방식이 확정안처럼 보이지 않도록 발표 표현을 비교·후보 중심으로 다시 요청했다.

## 6. 사람이 직접 수정한 것과 이유

수현은 AI 초안에서 빠진 Wiki 개요를 직접 작성했다. 아윤은 [AppText 태그 형식](https://github.com/snuhcs-course/swpp-2026-project-team-15/blob/main/android/MyLittleChef/app/src/main/java/com/example/mylittlechef/ui/components/AppText.kt#L1)을 다시 설계하고 레시피 화면·ViewModel을 직접 작성했으며 Figma 값을 바로잡았다. 혁준은 최종 발표 문구와 팀 결정사항을 확인했다. 코드 주석은 확인된 AI 초안의 출처를 표시한다. 연구 코드는 AI 작성 줄을 특정할 근거가 없어 줄 단위 attribution을 하지 않았다. 이 작업에는 프로젝트 맥락과 사람의 판단이 필요했다.

**다음 Iteration:** 원본 데이터, 실사진 결과, 팀 결정, AI 초안을 구분해 기록한다.
