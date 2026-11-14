# 원문·썸네일 저장 및 재개 운영 안내

도구는 목록 한 페이지의 파일럿과 `--full`을 사용한 9개 분류·고유 출처 ID 500개 본수집을
지원한다. 원본 HTML/JSON·검증된 썸네일·관찰 경로·개별 오류를 보존하며 중단 후 재개한다.
`acquisition_complete`는 정확한 quota와 필수 파일 검사를 통과해야 true다. 의미 중복 검수와
서비스 적합성 검수는 별도 작업이다. 실제 사이트 실행은 별도 요청 후 운영자가 수행한다.

## 실행 전 확인

실수집 전 현재 사이트의 robots/약관과 의도한 이용 범위를 확인한다. 공개 접근 가능성은
본문·이미지 재배포나 AI 입력 이용 허가를 뜻하지 않는다. 검토 메모는 선택적으로 별도 보관한다.
CLI는 `--live`만 실행 opt-in으로 사용하며 source-use-review 입력·승인 판정을 요구하지 않는다.
아래 live 명령은 운영자가 실제 수집을 요청한 경우에 실행한다. 테스트는 이를 실행하지 않는다.

`tools/`에서 도움말은 오프라인으로 확인할 수 있다.

```powershell
uv run --locked python -m crawlers.tenkrecipes.cli collect --help
uv run --locked python -m crawlers.tenkrecipes.cli resume --help
```

## 수집과 재개

다음 예시는 밥/죽/떡(cat4=52)의 첫 페이지를 저장한다. `--category` 기본값은
밑반찬(63), `--page` 기본값은 1이다. 분류는 승인된 9개 cat4 중에서 선택한다.
목표 plan은 계속 500개를 기술하지만 이 명령은 해당 quota를 채우는 작업이 아니다.

```powershell
uv run --locked python -m crawlers.tenkrecipes.cli collect --output-dir ../data/tenkrecipes/runs/pilot --category 52 --page 1 --live
uv run --locked python -m crawlers.tenkrecipes.cli resume --output-dir ../data/tenkrecipes/runs/pilot --live
```

collect는 기존 출력 디렉터리를 덮어쓰지 않는다. 출력 경계 검사는 plan과 동일하다.
resume은 현재 plan·parser/schema 버전·네트워크 정책이 저장된 값과 같은지 먼저 확인한다.
불일치하면 네트워크·기존 산출물 변경 없이 거부한다. 새 설정/파서는 새 실행 경로를 사용한다.
기존 데이터를 조용히 변환하거나 원문을 갱신하기 위해 manifest를 편집하지 않는다.

기본 네트워크 정책은 단일 동시 요청, 시작 간격 최소 2초, 연결/읽기 timeout 10/30초,
GET당 최대 3회다. 재시도 대상은 429, 일시적 500/502/503/504, timeout/연결 오류다.
Retry-After(초 또는 HTTP 날짜)를 우선하고 기본 요청 간격도 지킨다. 식별 가능한 User-Agent를
쓰며 세션 쿠키·환경의 인증 정보는 사용하지 않는다. 기본 transport는 HTTP redirect를 자동으로
따르지 않고 3xx를 HTTP 실패로 남긴다. 원본 호스트 외부로 요청을 확장하지 않는다.

기본 대기 상한은 60초, 실행별 HTTP 예산은 120초다. 필요하면 두 명령 모두에
`--max-wait`와 `--run-budget`으로 유한 양수를 지정한다. 재개 시 저장 정책과 같은 값을
사용해야 한다. 시간 예산은 다음 요청/대기 시작 전에 검사하며 진행 중 요청에는 별도의
10/30초 timeout이 적용된다. 프로세스를 새로 시작하면 실행 예산은 새로 시작하지만,
저장된 Retry-After의 `retry_not_before` 이전에는 재요청하지 않는다.
저장 원본의 재파싱·이미지 복구 같은 로컬 작업도 아직 유효한 대기 시각을 지우지 않는다.

## 상태와 산출물

| 상태 | 의미 |
|---|---|
| `running` | 현재 checkpoint가 정상이며 후속 작업 가능; 500개 취득 완료 아님 |
| `blocked` | 401/403, 알려진 challenge 표시 또는 목록 필터/selector 구조 이상 |
| `deferred` | 대기 상한·실행 예산 초과; 대기 시각과 이전 진행 보존 |
| `failed` | 비재시도 HTTP 실패 또는 유한 재시도 소진 |
| `incomplete` | 기록된 후보 처리를 마쳤지만 취득 실패가 남음; 전체 quota 검증 결과는 아님 |
| 상세 `parsed` | DOM 파싱 결과 저장; 필수 취득 조건/이미지/서비스 적합성 검증과 별개 |
| `image_validated` | 실제 디코딩과 크기 상한을 통과한 썸네일 원본 저장 |

차단 상태는 우회하지 않고 원인을 확인한다. 목록 구조 변화가 확인되면 현 parser로 반복 실행하지
말고 parser 변경과 새 버전의 오프라인 검증을 진행한다. CLI는 차단·대기·실패를 nonzero로
종료하고 출력 경로·상태·원인을 JSON으로 알린다. 후보별 실패는 manifest에도 남는다.
CLI와 `resume_pending(include_images=True)`는 빈 제목·이름 있는 재료 부재·단계 본문 부재·
손상/과대 이미지 후보를 보존하고 같은 분류의 기록된 다음 후보로 진행한다. 수량 누락이나
등록 도구 부재는 제외 사유가 아니다. 상세의 제목 요소·재료/단계 영역 등 필수 DOM 구조가
없거나 상세 파싱/디코딩이 실패하면 `failed / structure_mismatch`로 원본을 보존하고 같은 분류의
다음 후보로 진행한다. 파싱 JSON이나 썸네일을 임의로 만들지 않는다. 목록 구조 이상은 중단한다.
한 페이지 파일럿은 기록된 후보까지만 처리한다. 본수집은 승인된 분류 순서와 추천순을 유지해
필요한 다음 페이지로 확장하고 quota 할당·개별 오류·미달을 보고한다.

## 파일럿 이후 본수집과 검수 전달

목표는 다음과 같고, 각 요청은 `cat2=18`, `order=reco`를 유지한다. 추천순을 월간 순위로
표현하거나, 부족한 quota를 다른 분류에 옮기거나, 필터를 넓히지 않는다.

| 순서 | 종류 | cat4 | 목표 |
|---|---|---|---:|
| 1 | 밑반찬 | 63 | 100 |
| 2 | 메인반찬 | 56 | 90 |
| 3 | 국/탕 | 54 | 60 |
| 4 | 찌개 | 55 | 30 |
| 5 | 면/만두 | 53 | 60 |
| 6 | 밥/죽/떡 | 52 | 100 |
| 7 | 퓨전 | 61 | 20 |
| 8 | 양식 | 65 | 20 |
| 9 | 샐러드 | 64 | 20 |

1. 실행 전 이용 범위를 확인하고 위 한 페이지 명령으로 작은 파일럿을 실행한다. 필터·DOM·
   이미지 호스트 및 저장된 원본/파싱 결과를 확인한다. 자동 검증이 본문·이미지 재배포나 AI
   이용 권한 또는 원문 의미의 정확성을 승인해 주지는 않는다.
2. 같은 스키마·parser·네트워크/이미지 정책의 파일럿이면 `resume --full`로 본수집으로 확장할
   수 있다. 저장된 페이지와 결과를 재사용하되 할당은 아래 고정 분류 순서를 따른다. 새 실행은
   `collect --full`을 사용한다. 본수집에 `--category`/`--page` 변경을 결합하지 않는다.
3. 예산 초과·429는 대기 시각 이후 재개하고, 접근/구조 이상은 원인을 확인한다. 운영자 확인
   상태는 아래 절차로 해제한다. 정상 빈 목록은 `exhausted`, 새 ID가 없는 반복 페이지는
   `repeated_page`로 보고하고 반복 순회를 중단한다. 미달을 500개 성공으로 표시하지 않는다.
4. 오프라인 `validate`로 파일·할당을 검사하고 `report`로 JSON/CSV를 생성한다. 미완료 exit
   code는 1, 입력 자체를 읽을 수 없으면 2다. 실행별 120초 기본 예산은 본수집 전체 시간을
   보장하지 않는다. 예산을 바꾸려면 처음부터 같은 유한 값을 사용한 새 run을 만든다.
5. `report.json`, `review.csv`, `manifest.json`과 원본 디렉터리를 함께 검수자에게 전달한다.
   보고서의 분류별 target/selected/deficit, failures, findings, 중단 원인을
   구분해 확인한다. CSV 제목 불일치의 observations 셀은 양쪽 제목·표현 종류·출처 URL의 JSON이다.

```powershell
# New full run; retain these finite budgets unchanged on resume.
uv run --locked python -m crawlers.tenkrecipes.cli collect --output-dir ../data/tenkrecipes/runs/full --full --live
uv run --locked python -m crawlers.tenkrecipes.cli resume --output-dir ../data/tenkrecipes/runs/full --live
# Alternatively, promote the compatible one-page pilot.
uv run --locked python -m crawlers.tenkrecipes.cli resume --output-dir ../data/tenkrecipes/runs/pilot --full --live
# These two commands are offline and do not require --live.
uv run --locked python -m crawlers.tenkrecipes.cli validate --output-dir ../data/tenkrecipes/runs/full
uv run --locked python -m crawlers.tenkrecipes.cli report --output-dir ../data/tenkrecipes/runs/full
```

본수집 모드는 manifest에 기록되어 이후 `resume`에는 `--full`을 반복할 필요가 없다.
동일 ID는 최초 성공 분류에 한 번만 할당하며, 후순위 분류는 자기 다음 후보를 검토한다.
다른 ID는 이름·내용·이미지가 같아도 합치지 않는다. 초과 관찰은 남기되 quota에는 넣지 않는다.
개별 후보 오류는 ID·URL·사유·분류/페이지/순서·원본 경로를 남기고 다음 후보로 진행한다.
A→B 대체 관계는 새로 만들지 않는다. `replacements`는 기존 run 호환용 필드이며 과거 값은
보존한다. 중단/대기는 run 상태와 요청 이력에서 확인한다.

**500개는 서로 다른 출처 ID의 수이며 실질적으로 다른 요리 500개를 보장하지 않는다.**
의미 중복 검수는 `pending`이며 서비스 반영 전 반드시 수행해야 한다. 수량 보완·도구 요구·
자취 적합성과 이용 범위도 사람이 별도로 검토한다. 판정 기준·중복 통합/제외·서비스 CSV 변환·
정규화 재료 ID 매핑·DB import·이미지 배포는 이 도구의 범위에 포함되지 않는다.
report.json/review.csv는 각각 원자적으로 게시되지만 두 파일을 묶은 트랜잭션은 아니므로,
보고서 게시 중 중단되면 `report`를 다시 실행하고 두 파일을 함께 전달한다.

## 같은 run에서 카테고리별 quota 수집 후 종료

`--only-category CODE`는 지정 분류의 기존 quota까지 페이지를 순회하고 다음 분류를 요청하지
않은 채 종료한다. 첫 실행은 `collect`, 다음 분류부터는 같은 output 경로에 `resume`을 사용한다.
`--category`는 기존 한 페이지 파일럿 옵션이므로 혼용하지 않는다. `--full`과도 함께 쓸 수 없다.
고정 분류 순서·출처 ID 우선순위를 유지하므로 앞선 분류가 quota 도달 또는 소진된 후 다음
분류를 지정한다. 앞선 분류가 미처리 상태면 요청·진행 기록 변경 전에 거부한다.

```powershell
# Fill side dishes (100), then exit. These examples are operator live commands.
uv run --locked python -m crawlers.tenkrecipes.cli collect --output-dir ../data/tenkrecipes/runs/by-category --only-category 63 --run-budget 600 --live
# Fill main dishes (90) in the same run, then exit.
uv run --locked python -m crawlers.tenkrecipes.cli resume --output-dir ../data/tenkrecipes/runs/by-category --only-category 56 --run-budget 600 --live
# Resume only the last requested category after a bounded stop.
uv run --locked python -m crawlers.tenkrecipes.cli resume --output-dir ../data/tenkrecipes/runs/by-category --run-budget 600 --live
# Explicitly return to full traversal if desired.
uv run --locked python -m crawlers.tenkrecipes.cli resume --output-dir ../data/tenkrecipes/runs/by-category --full --run-budget 600 --live
```

분류 코드는 위 표의 순서인 `63 → 56 → 54 → 55 → 53 → 52 → 61 → 65 → 64`다.
실행 예산 안에 quota를 채우지 못하면 동일한 설정으로 같은 분류를 재개한다. 마지막 지정
분류는 manifest의 선택 필드 `quota_category`에 저장되어 옵션 없는 재개도 그 범위를 유지한다.
`--full`은 이 범위를 해제한다. 완료 분류를 다시 지정하면 검증된 결과를 재사용하고 종료하며,
다른 분류의 누락 자산을 네트워크로 복구하지 않는다. 원본·할당·분류 간 중복 ID 기록은 공유한다.

명령의 JSON 출력은 `requested_category`와 `category_complete`를 제공한다. 지정 분류가
검증된 quota에 도달하면 exit 0이며, 소진·차단·대기·미달은 nonzero다. 전체 `state` 및
`report.json`/`review.csv`는 계속 500개 목표의 검증 결과를 나타내므로 분류 하나가 완료되어도
`state=incomplete`, `acquisition_complete=false`일 수 있다. 전체 완료는 9개 quota와 파일 검사가
모두 통과해야 한다. 기존 schema 4 run에도 적용되며 parser·네트워크/이미지 정책은 동일해야 한다.

기존 카테고리별 3개 파일럿도 같은 경로에 `resume --only-category 63 --run-budget 600 --live`
로 이어갈 수 있다. 별도로 만든 `pilot-summary.json`/`pilot-selection.csv`는 당시 27개 파일럿의
스냅샷이며 이후 CLI 수집에서 갱신되지 않는다. 최신 상태는 manifest와 report에서 확인한다.

## 오류 중단과 운영자 확인

- 허용 밖 이미지 호스트 또는 redirect 한도 초과는 즉시 `blocked`로 중단한다.
  `operator_review_required: true` 및 `operator_notice`에 원인·출처 ID·레시피/이미지 URL을 남긴다.
- 레시피 상세나 썸네일의 5xx·연결 오류가 GET당 총 3회 재시도를 소진하면 해당 후보의 실패를
  보존하고 다음 후보로 진행한다. 서로 다른 출처 ID **3건 연속**이면
  `reason: consecutive_network_failures`로 중단하고 해당 ID 목록을 알린다.
- 레시피 내부 재시도를 별도 실패 건수로 세지 않는다. 상세·썸네일 취득 성공 시에만 연속 횟수를
  초기화한다. 콘텐츠 결격과 이미지 형식 실패는 횟수에 넣지도, 기존 횟수를 초기화하지도 않는다.
  과거 완료 파일의 재생성도 새 성공으로 중복 집계하지 않는다.
- `candidate_outcomes`와 `network_failure_streak`를 checkpoint에 저장하여 재개 후 실패 후보를
  재집계하거나 이미 소진한 요청을 다시 실행하지 않는다. 429·Retry-After·실행 예산은 별도
  대기 정책을 유지한다. 목록 요청/구조 실패와 401/403/challenge는 건너뛰지 않는다.

상세 구조 실패는 네트워크 연속 실패 횟수를 늘리거나 초기화하지 않는다. 이전 schema 4 run에
상세가 `blocked / structure_mismatch`로 남아 있으면, 향후 실제 후보 처리 시 저장 원본의 해시를
확인하고 재요청 없이 `failed`로 전환한다. 원본을 보존하고 최종 오류를 간단히 남긴다.
다음 성공 후보와 대체 관계를 만들지 않는다. 코드 변경이나 오프라인 validate/report만으로
run을 전환하지 않는다.
이 정책 변경은 schema 4·parser 출력 계약을 유지하며 별도 실수집 요청 전에는 재개하지 않는다.

운영자 확인이 필요한 중단은 재실행만으로 해제되지 않는다. 원인을 확인한 뒤 다음과 같이
명시적으로 해제한다. 확인은 허용 호스트나 이미지 제한을 완화하지 않으며, 원인이 그대로면
다시 중단한다. 고정 정책을 바꿔야 한다면 새 run을 사용한다.

```powershell
uv run --locked python -m crawlers.tenkrecipes.cli resume --output-dir ../data/tenkrecipes/runs/pilot --live --acknowledge-stop
```

`acknowledge_stop()`은 API의 같은 확인 동작이다. 연속 실패 중단을 해제하면 횟수를 초기화하고
실패 기록은 보존한 채 다음 미처리 후보로 진행한다. 유효한 Retry-After는 해제하지 않는다.
여기서 알림은 CLI의 JSON 진단과 nonzero 종료 코드이며 외부 메시지 전송은 하지 않는다.

```text
run.json                       고정 plan, run ID, 시작 시각, parser/schema 및 네트워크 정책
manifest.json                  후보 관찰, 목록·상세 상태, 시도 이력, 대기 시각
report.json                    목표·파일 검사·미달·실패/대체·검수 대기 보고서
review.csv                     검수 finding·실패 및 원본/JSON/이미지 연결
failure.pending.json           실패 checkpoint 교체 중단 시 복구할 상태 (정상 게시 후 제거)
lists/<cat4>/<page>.html        성공적으로 파싱한 목록 원본
lists/<cat4>/*.failed-*.html    실패/차단 응답 원본 (성공 목록으로 사용하지 않음)
details/<source_id>.html        상세 원본
details/*.failed-*.html         실패/차단 상세 응답
recipes/<source_id>.json        구조화한 파서 결과
images/<source_id>.<format>     검증된 썸네일 원본 바이트
images/*.meta.json             검증 정보와 중단 복구용 provenance
attempts/<attempt_id>.html      응답이 있었던 각 HTTP 시도의 원본
*.html.meta.json               run/source/해시/시도 provenance sidecar
```

manifest는 최종 URL·취득 시각·상태·본문 해시를 보존하고 응답 헤더/쿠키/예외 메시지는
기록하지 않는다. 전송 실패는 예외 종류만 기록한다. 여러 시각에 수집한 페이지를 한 시점의
사이트 전체 순위로 해석하지 않는다. 원문과 완료 결과는 재개 시 해시 검증 후 재사용한다.
동일 출처 ID를 새 페이지나 분류에서 다시 관찰해도 이미 검증한 이미지 상태를 공유하며,
각 관찰의 페이지·분류·위치는 별도로 유지한다.

## 중단 복구와 한계

raw/JSON/manifest는 같은 디렉터리의 임시 파일을 flush/fsync한 뒤 atomic replace로
게시한다. 파일 게시에 실패하면 이전 manifest가 유지된다. 원문은 덮어쓰지 않는다.
실패 결과는 `failure.pending.json`에 먼저 기록한 뒤 manifest로 게시한다. manifest 교체가
중단되면 재개 시 run ID·참조 파일을 검증하고 실패 상태·미완료 요청·대기 시각을 복구한다.
응답 본문이 없는 전송 실패도 이 경로로 보존한다. 정상 게시 후 임시 복구 기록을 제거한다.
이 기록이 저장되기 전의 요청/파일 저장 중단까지 보장하는 것은 아니다.
원문 sidecar는 본문보다 먼저 저장하여, 본문 게시 후 manifest 교체가 중단돼도 저장 원본을
검증할 수 있다. 재개는 이러한 완료 목록을 복원하고, 파싱 JSON만 없으면 저장된 상세 HTML에서
재생성한다. 미완료 상세는 다시 취득하며 실패한 목록 요청도 기록된 범위에서 재개한다.
원본 sidecar를 재사용할 때는 최종 성공 응답뿐 아니라 중간 재시도 응답 파일도 해시로
검증하고 manifest의 응답 목록에 복구한다. 해당 응답 파일이 누락되거나 손상되면 중단한다.
처음 요청하지 않은 새 페이지를 재개 명령이 자동 탐색하지는 않는다.

완료 원본이나 존재하는 파싱 JSON의 해시가 다르면 `IntegrityError`로 거부하고 덮어쓰지 않는다.
원본이 손상되면 보존한 채 원인을 확인하고 새 run에서 다시 수집한다. 하나의 run에는 하나의
운영자 프로세스만 접근한다. 다중 writer 잠금과 모든 파일시스템의 전원 장애 내구성을 보장하지
않으며, 요청 중 강제 종료로 아직 응답이 저장되지 않았다면 해당 미완료 요청은 다시 필요할 수 있다.

Python API는 `CollectionRun.create/resume`, `fetch_list`, `fetch_detail`, `resume_pending`,
`collect_quotas`, `snapshot`을 제공한다. API로 다음 페이지를 요청할 때도 저장 후보 처리를 우선한다.
Python API의 `resume_pending()`은 기존처럼 상세만 처리한다.
`resume_pending(include_images=True)`와 CLI는 검증된 썸네일까지 취득·재개한다.
`collect_quotas()`는 고정 순서의 페이지 순회·quota 할당과 보고서 게시까지 처리한다.
`collect_quotas(category_code="63")`는 해당 분류만 처리한다. API에서 scope 사전 검증이
필요하면 `CollectionRun.resume(..., category_code="63")`를 사용한다. API의 인자 없는
`collect_quotas()`는 전체 순회이며, 마지막 scope를 기억하는 동작은 CLI resume가 제공한다.

## 썸네일 계약

목록에서 선택해 기록한 `thumbnail_url`만 요청한다. 동영상 배지·작성자 사진·상세 대표
이미지·단계 사진은 썸네일로 대체하지 않는다. URL 접미사를 바꾸거나 확대·재인코딩하지 않는다.
확장자는 URL이 아닌 Pillow가 검출한 실제 형식을 사용한다(예: JPEG는 `.jpg`).

기본 허용 호스트는 관찰된 `recipe1.ezmember.co.kr`과 원본 사이트
`www.10000recipe.com`/`10000recipe.com`이다. 각 리다이렉트의 대상 URL을 요청 전에 검사한다.
다른 호스트는 자동 허용하지 않는다. 기본 상한은 응답당 10 MiB, 20,000,000픽셀,
리다이렉트 3회다. 이는 취득 자원 제한이며 서비스 적합성 필터가 아니다.
API의 `ImageDownloader(..., allowed_hosts=..., max_bytes=..., max_pixels=..., max_redirects=...)`
에서 변경할 수 있으며, 고정된 `image_policy`를 run.json에 저장한다.

썸네일 요청도 HTML과 같은 `HttpClient`의 단일 동시 요청·간격·retry·전체 예산을 사용한다.
응답을 bounded chunk로 임시 파일에 읽으며 Content-Length와 실제 바이트 수를 검사한다.
Content-Type은 출처 정보로 보관하되 실제 형식은 Pillow로 검증하고 첫 프레임을 디코딩한다.
과대 응답·손상·HTML·전송 중단은 정상 이미지 파일로 확정하지 않는다.

manifest의 `images[source_id]`에는 상태·원본/최종 URL·레시피 출처 URL·실제 포맷·가로/세로·
바이트 수·SHA-256·취득 시각·로컬 상대 경로·시도 이력을 저장한다. 검증된 이미지는 같은 ID로
재다운로드하지 않고, ID가 다르면 바이트 해시가 같아도 별도 파일과 출처를 유지한다.
게시 후 checkpoint가 중단된 이미지는 sidecar와 해시로 복원하며, 없는 파일만 다시 취득한다.
기존 파일의 해시가 바뀌면 덮어쓰지 않고 중단한다.

현재 run 스키마는 `4`, parser 버전은 `tenkrecipes-dom-2`다. 할당·오류·분류별 진행과
파일럿/본수집 모드를 저장하므로 이전 버전 run은 자동 변환하지 않고 새 실행 경로를 사용한다.
재개 시 이미지 정책도 동일해야 한다. 300×300 입력은 그대로 보존된다.

### Simple candidate errors (2026-11-15)

Detail/thumbnail HTTP errors such as 404, transport errors, content failures and
invalid images are logged once and skipped. Terminal logs and candidate outcomes
share one checkpoint. Legacy nonterminal rows are replaced only when that candidate
finally fails; original request/response artifacts remain intact. No new replacement
links or terminal logs for pauses/stops are generated.

429/Retry-After and run budgets, denial/challenge, list errors, image host/redirect
limits and three consecutive recipe network failures retain their stop/defer rules.
