# Iteration 1 AI 사용 기록 — 최재혁 (PM 정리)

PM에 따르면 재혁은 Iteration 1의 연구·AI 파이프라인 탐색에 **Codex**를 사용했다. 이 기록은 PM의 진술과 일정표·Git/Wiki 산출물을 구분해 정리한다. 코드나 Wiki만으로 AI가 작성한 범위까지 특정하지 않는다.

## 1. AI 사용 영역

- 일정표의 `A1`은 “Compare vision-to-recipe pipeline candidates using simulated ingredient mentions”이며 재혁이 Worker로 기록되어 있다. 완료일은 2026-10-02, `AGENT HOURS`는 1.0, 관련 커밋은 [`4ea64e3`](https://github.com/snuhcs-course/swpp-2026-project-team-15/commit/4ea64e3)이다.
- 해당 커밋에는 `research/benchmark_suite.py`, P0~P5 파이프라인, 연구용 레시피 집합과 결과 JSON이 포함된다. [연구 설계와 비교 Wiki](https://github.com/snuhcs-course/swpp-2026-project-team-15/wiki/Pipeline-Candidate-Comparative-Evaluation)는 재혁이 10월 2일에 게시했다([Wiki 커밋 `297279a`](https://github.com/snuhcs-course/swpp-2026-project-team-15.wiki/commit/297279a)).
- `P3`에는 재혁이 Worker로 참여했고, `P6`은 Incomplete, `P7`은 Hold다. 미완료·보류 작업을 완료된 AI 산출물로 설명하지 않는다.
- 정확한 Codex 모델 버전과 의도적으로 AI를 사용하지 않은 작업은 현재 자료에 기록되지 않았다.

## 2. 실제 프롬프트 기록

재혁이 10월 2일 사용한 프롬프트 문구:

> P0부터 P4까지 파이프라인 비교를 코드를 통해 제작해보았는데, 이를 바탕으로 최종적으로 선택한 파이프라인들을 토대로 P5를 구성해줘.

## 3. AI가 잘한 일

연구 코드에는 비교 가능한 파이프라인 구조와 벤치마크 실행 절차가 있다. 위 프롬프트는 P0~P4 비교를 바탕으로 P5 구성안을 요청한 사례다. 코드 중 Codex 기여 부분이나 절약 시간은 산출물만으로 구분되지 않는다.

## 4. AI 오류·환각

연구 결과는 모의 재료 문자열을 사용하며 실제 냉장고 사진 인식 성능이 아니다. 이는 결과 해석의 한계이며, 재혁이 경험한 Codex 오류로 단정하지 않는다. 개별 AI 오류 사례는 현재 기록에 없다.

## 5. 수정한 프롬프트

원문 전후와 수정 이유가 현재 자료에 없어 실제 프롬프트 수정 사례를 적지 않는다.

## 6. 직접 고친 내용과 이유

직접 수정한 코드·문서·측정값과 Codex 초안의 경계는 현재 자료만으로 구분되지 않는다. 따라서 특정 코드를 사람이 고쳤다고 주장하지 않는다.

## 기록 보완에 필요한 원자료

1. 위 P5 요청 외 다른 Codex 프롬프트가 있다면 해당 원문.
2. Codex가 작성한 파일·범위 및 직접 수정한 부분.
3. 오류 사례, 발견 방법, 수정 시간, 프롬프트 수정 전후.
4. AI 미사용 작업과 코드 attribution 주석을 둘 위치.
