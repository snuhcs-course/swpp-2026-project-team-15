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

## 남은 통합 선택

이름→ID의모호함/unknown·catalog 검증, 새 original/revisionDTO, partial/refused/failed/not_attempted·empty·transport 구분, 정렬/count·전체 timeout/cancel/retry·favorite 상세복원이 남았다. revised는 의미정확/안전보증아니다. 도구/알레르기 data·분량·안전한 AI 수정범위/고지/비용, public deployment/공유동기화는 별도근거가 필요하다.

다른팀원에 새의무·마감을 부여하지 않는다. 실제정책변경의 날짜·이유·PR/근거·결과를 기록하고 공식 Wiki를 별도갱신한다. 코드 PR은 Wiki 게시가 아니다.
