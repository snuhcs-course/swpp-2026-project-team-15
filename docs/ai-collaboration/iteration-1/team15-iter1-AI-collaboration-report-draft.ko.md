# AI 협업 보고서 — Iteration 1 (2026-09-23~2026-10-09)

**작성:** 권혁준(PM) · **참여:** 안수현, 최아윤, 최재혁  
**도구:** 수현—Codex(GPT-6.1 Sol), 아윤—Claude 채팅(Sonnet 5.5), 혁준·재혁—Codex(모델 버전 기록 없음).

## 1. AI를 사용한 곳

수현은 레시피 ER 모델, 엔티티 CSV, `server/db/schema.sql`, `server/db/import_recipes.py`, DB Wiki 초안에 Codex를 사용했다. 아윤은 Android 내비게이션, 온보딩, 냉장고, 촬영·분석·직접 입력 화면 일부의 초안에 Claude를 사용했다. 레시피 화면과 ViewModel은 직접 작성했다. 혁준은 PM 인수인계 문서, TA 발표 초안, Mermaid 도표, 제출 문서 Markdown 표현에 Codex를 사용했다. PM에 따르면 재혁은 [연구 코드](https://github.com/snuhcs-course/swpp-2026-project-team-15/commit/4ea64e3)와 [연구 Wiki](https://github.com/snuhcs-course/swpp-2026-project-team-15/wiki/Pipeline-Candidate-Comparative-Evaluation)로 이어진 AI 파이프라인 탐색에 Codex를 사용했다. 산출물만으로 Codex가 작성한 코드 줄을 특정할 수는 없다. **작업 담당자, 추가 일정표 Task, 완료 범위는 팀과 PM이 직접 결정했다.**

## 2. 실제 프롬프트 기록

- 수현(10월 5일): “server/db/ 아래 스크립트부터 작성해 봐야할듯. csv 입력을 받는 스크립트부터 작성해.”
- 수현(10월 6일): “음.. 그럼 재료 타입 코드까지 활용해서 recipeingredient의 키로 쓰는 건?”
- 아윤(10월 4일): “이제 CaptureScreen, AnalyzeScreen, ManualAddScreen을 만들어보자.”; “카메라 X 적용해줘”
- 혁준(10월 9일, PM이 제공한 문구): “다음 md 내용을 시각화해서 mermaid로 표현해줘”
- 재혁(10월 2일): “P0부터 P4까지 파이프라인 비교를 코드를 통해 제작해보았는데, 이를 바탕으로 최종적으로 선택한 파이프라인들을 토대로 P5를 구성해줘.”

긴 원문은 [통합 프롬프트 로그](team15-iter1-prompt-log-draft.md)에 따로 모았고, [수현](iter1_AI_report_soohyun.md), [아윤](iter1-AI-report-ahyoon.md), [혁준](iter1_AI_report_hyeokjun.md), [재혁](iter1_AI_report_jaehyuk.md)의 개인 기록에서 맥락을 볼 수 있다.

## 3. AI가 잘한 점

수현의 보고에 따르면 AI가 만든 SQL 스키마와 CSV 입력 스크립트는 수동 코드 수정 없이 실행됐다. 현재 로컬 DB는 레시피 537개, 단계 2,870개, 레시피-재료 관계 5,933개를 입력할 수 있다. 아윤의 보고에 따르면 AI가 Figma 프레임 6개를 화면 4개와 재사용 상태로 정리해 약 3시간을 절약했다. 공용 `EditableIngredientList` 설계도 중복을 줄였다. PM 업무에서는 인수인계 확인 항목과 발표 선택지를 검토 가능한 초안으로 정리했다. PM 작업의 절약 시간은 측정하지 않았다.

## 4. 오류·환각

수현은 `[불고기양념] 간장` 같은 접두어가 재료 이름에 남아 같은 재료가 중복될 위험을 CSV 수동 검사에서 발견했다. 정규화된 이름과 원본 이름을 분리했다. 아윤은 온보딩 초안의 `rememberSaveable` 타입과 누락된 import를 확인했고, 의존성 안내 후 발생한 Kotlin 메타데이터 불일치를 Gradle 빌드에서 발견했다. Codex는 혁준의 개인 초안 작성 시점을 모르고 문서 개정 이력 세 날짜를 모두 10월 9일로 적었다. PM이 실제 날짜를 제공해 [수정했다](https://github.com/snuhcs-course/swpp-2026-project-team-15/commit/9eff8d1). 정확한 수정 시간은 기록되지 않았다.

## 5. 수정한 프롬프트

아윤은 “텍스트 중간의 특정 글자에만 색이 넣고 싶으면 어떻게 해”에서 “그냥 텍스트에 태그로 받아서 AppText가 파싱하는 방식이면 안되냐”로 바꿨다. 태그라는 입력 형식을 명시해 같은 단어가 반복될 때의 모호함을 줄였다. 혁준은 미확정인 백엔드·재고 저장 방식이 발표에서 확정안처럼 읽히지 않도록 비교·후보 표현을 다시 요청했다.

## 6. 사람이 직접 수정한 것과 이유

수현은 AI 초안에서 빠진 Wiki 개요를 직접 썼다. 아윤은 `AppText` 태그 방식, 레시피 화면·ViewModel, Figma의 색상·치수를 직접 수정했다. 혁준은 발표 최종 문구와 팀 결정사항을 확인하고 Mermaid 도표를 Word용으로 직접 캡처하기로 했다. 해당 작업은 프로젝트 맥락, 시각적 판단 또는 팀의 결정 권한이 필요했다. AI 생성 코드의 attribution 주석은 각 코드 담당자가 생성 범위를 확인한 뒤 추가해야 한다.

**다음 Iteration:** 원본 데이터, 실사진 평가, 팀의 결정, AI 초안을 구분해 기록하고 구현 요청에는 스키마·대상 파일을 먼저 제공한다.
