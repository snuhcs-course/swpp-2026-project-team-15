# Revision Judge 실험 보고서 — 2026-11-22

- [Judge–사람 채점 비교](judge-human.md)
- [프롬프트 수정 전후 비교](prompt-comparison.md)
- [사용자 독립 채점 원문](human-evaluation.md)
- [미채택 프롬프트 변경 diff](prompt-change.diff)

기존 ignored `output/`의 보고서를 공유 가능한 경로에 복사했다.
사용자 원문과 점수는 그대로 보존하고, 보고서 링크·자료 위치 및 미채택 상태만 정리했다.
프롬프트 변경은 성능 개선이 확인되지 않아 revert 대상이며, 코드에 적용하는 패치가 아니다.

변경 규모를 제한하기 위해 전체 runner observation, 레시피 및 provider raw JSON은
이 묶음에 복제하지 않았다. 해당 자료는 각 보고서에 명시된 로컬 output 경로에 남아 있으며,
이 디렉터리만 받은 독자는 원본 응답을 완전히 재검증할 수 없다.
단, 사람 점수·Judge 점수·비교 지표·판정 근거·실행 조건과 프롬프트 변경은 본 묶음에서 확인 가능하다.
