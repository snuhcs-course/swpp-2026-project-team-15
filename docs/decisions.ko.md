# 결정 로그 — 현재 유효 상태

[English](decisions.md) · [한국어](decisions.ko.md)

2026-10-20 main `a27bf0a` 및 최신 검토 branch 기준으로 다시 정리했다. 과거논의는 [회의록](meetings/README.ko.md)과 [b1e508a의 이전로그](https://github.com/snuhcs-course/swpp-2026-project-team-15/blob/b1e508af2be675ac6cad5403ace3d7e2fb1a49d2/docs/decisions.ko.md)에 보존된다. 구현/미병합/제안을 구분한다.

| 항목 | 현재 적용과 경계 |
| --- | --- |
| 방향 | 소가구·사진후보확인→재고→추천/상세. 1 인분/도구/알레르기 전체구현은 아님 |
| Backend | 10-11 선택 FastAPI/SQLModel/uv/SQLite는 PR #6 병합. PostgreSQL/Redis/Docker/public deployment는 제안 |
| 로컬 demo | laptopserver/USB 폰 adb reverse. script는 DB 존재시재생성안함. 기존자원·버전확인필요 |
| 인식 | mock/Gemini provider. mock은 imagehash fixture 선택. 과거 model 지원/20of26은 날짜제한관측 |
| main 추천 | 이름·소수동의어·상비양념 10 종·재고최소 1·기본부족 3. 새 ID/revision 정책과 다름 |
| 저장 | main 메모리. 혁준 88d3380 및 ancestor에 DataStore/VM 구현. 기술미결정이나 main 완료로 쓰지 않음. favorite 상세복원불완전 |
| Android | min26/target 36/compile 37; Retrofit/Gson/OkHttp. compile 37은 현 AndroidX 때문 |
| 사진 | 10-14 client 최대 2048px·선택 EXIF 유지/GPS 제외·server 그대로. PM 무후처리전제와 차이. 표본 1090token을 비용불변으로 일반화금지, recall 영향미검증 |
| 테스트 | CIserverruff/pytestcov·Androidlint/JVM/JaCoCo, device 별도. 기본판 33pass/95%, 과거 Android2%는 새통합측정아님 |
| Catalog | old 701/new 560; 공유 ID의미변경. matching schema/importer·별도 DB 검증필요. 재배포권한미확인 |
| AI 보고 | 최신 v1.1. 모든 AI 파일표기의무없음, 수동수정위치주석은 유용한경우. 과거 attribution/prompt 보존 |

## 2026-10-20 feature branch 통합 결정

혁준88d3380/1edadc0·수현89fc8ba의 commit/tests를 보존해 main a27bf0a 기반으로 병합했다. 위 표는 main 기본판의 기존 결정이며 현재 feature branch의 변경은 다음과 같다.

- 별도560종 DB·catalog version과 이름→ID adapter로 구형701종 ID 혼용을 차단한다. unknown/ambiguous 이름을 고지하며 이름 기반 DataStore를 유지한다.
- 신규 ID API/DTO를 실제 앱에 연결하고 legacy API는 호환용으로 보존했다. 물만 가정하며 정렬용 부족 count와 전체 미보유 목록을 구분한다.
- original/AI 상태·제안을 분리하고 read210/call240초, cancellation/generation guard·자동재시도없음으로 요청을 관리한다. 즐겨찾기는 AI 호출 없이 원본을 복원한다.
- 원본테스트 유지·확대 runtime coverage·결합flow/reopen/device 시나리오 및 pre-commit을 검증했다. [계약](iterations/iteration-2/integration-contract.md)·[실행기록](iterations/iteration-2/execution-report.md) 참조.
- 도구/알레르기·1인분/출처URL·의미평가는 미완성이다. Docker/nginx는 사용자 결정으로 Iter3 준비에 이월한다.

main 병합·공식 Wiki·타인review는 별도이며 팀원에게 새의무/마감을 부여하지 않는다.
