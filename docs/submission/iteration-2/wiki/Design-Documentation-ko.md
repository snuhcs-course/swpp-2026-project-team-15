# Design-Documentation — 한국어 안내

2026-10-20 통합 실행을 반영한 최신 기준은 [영문 게시 원고](Design-Documentation.md)다. 이전 한국어 초안은 [보존본](../../agent/archive/iter2-execution-docs/Design-Documentation-ko.md)에 있다.

main a27bf0a를 기반으로 혁준88d3380·수현89fc8ba를 원본이력 보존해 통합했다. 이름→ID·catalog버전·새응답/AI상태·정렬/요청취소·favorite원본복원과 시나리오 테스트를 연결했다. 기존테스트는변경하지않았다. 서버179pass/확대coverage98%, JVM 34pass, S22연결10pass이며 실제AI결과와mock은별도기록한다. 도구/알레르기·조리안전·의미정확성·sourceURL·1인분변환은완료주장하지않는다.

원본/AI제안은구분하고 DataStore·정렬·filtering/revision 원작을보존한다. pre-commit/테스트강화까지수행하며 Docker/nginx는Iter3준비로이월한다. 공식Wiki/Sheet/eTL는agent읽기전용이며사용자가반영한다. 최종PR·CI·실제review/merge·게시/제출은각각실제근거로완료확인한다. 영문원고버전: 0.6.
