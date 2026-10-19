# PM 인수인계와 운영 안내

[English](pm-handoff.md) · [한국어](pm-handoff.ko.md)

2026-10-20 Iter2 기준이다. 기존 일정의 Iter1 PM 권혁준/Iter2 PM 최아윤을 인용하며 이후순번은 최신일정을 확인한다. 새 의무·마감을 팀원에게 부여하는 문서가 아니다.

## 현재 인수인계

PR #6은 main `a27bf0a`에 병합됐다. Android·DB·연구가 main에 있고 로컬 FastAPI 흐름은 상세까지 동작한다. 이 feature branch에는 혁준88d3380(backend1edadc0·#9/#10 포함)과 수현89fc8ba를 원작 이력 보존으로 통합했다. catalog·이름→ID·DTO·상태·정렬·요청수명·즐겨찾기 원본복원을 구현·검증했다. main 병합/타인review·공식문서게시와 별도다. [통합근거](iterations/iteration-2/README.md)를 참조한다. [root README](../README.md)에 SHA·실행·제약이 있다.

## 근거와 절차

- 일정·실제작업자·시간/토큰·최종 commit은 팀 schedule이다. 에이전트는 **READ-ONLY**이고 로컬 반영안만 준비한다. P 번호를 보존하고 추가 A 번호는 PM이 확정한다. 측정하지 않은 시간을 만들지 않는다.
- 구현/review/merge는 GitHub, 실제회의시간/핵심논의는 [회의록](meetings/README.ko.md), 지속선택은 [결정로그](decisions.ko.md)와 Wiki에 기록한다. [Iter1 현황](iterations/iteration-1-status.ko.md)은 당시기록이다.
- 요구/API·Testing Plan→구현/unit/regression→branch push/PR→review/merge→main 핵심흐름재검증 순이다. 실제결과와 미완료계획을 구분한다.
- Requirements/Design/Testing/AI Report를 실제 SHA·증거와 맞춘다. Testing은 Plan/Results·명령·수·coverage·목표/제외·그림을 남긴다. AI는 v1.1, 일괄주석의무없음이다. ≥30frozen AI cases는 Iter3 다.
- 코드와 Wiki는 별도 Git이다.10-20 조회공식 Wiki는 10-09revision이다. 게시/readback, iteration-2-demo/README/영상, WikiPDF/scheduleXLSX, eTL 실제제출을 별도확인한다. 초안은 제출완료가 아니다.
- 개인대화원문·CSV·생성 DB·key는 Git에 넣지 않는다. 데이터재배포·새의존성·유료호출권한을 확인하고 최초 UI/기여를 보존한다. 미해결정책·PR·근거·접근상태를 후임에 전달한다.
