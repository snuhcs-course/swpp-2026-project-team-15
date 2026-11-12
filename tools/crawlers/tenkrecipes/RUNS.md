# 원문·썸네일 저장 및 재개 운영 안내 (4단계)

현재 도구는 지정 목록 **한 페이지**와 그 후보들의 상세 HTML/JSON·검증된 원본 썸네일을 취득한다.
500개 quota 할당·자동 페이지 확장·서비스 반영은 후속 단계다.
실행 결과의 `acquisition_complete`는 아직 항상 false다. 성공적으로 파싱됐다는 것은
서비스 적합성·의미 중복 검수·이미지 검증까지 완료됐다는 뜻이 아니다.

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

## 상태와 산출물

| 상태 | 의미 |
|---|---|
| `running` | 현재 checkpoint가 정상이며 후속 작업 가능; 500개 취득 완료 아님 |
| `blocked` | 401/403, 알려진 challenge 표시 또는 필터/selector 구조 이상 |
| `deferred` | 대기 상한·실행 예산 초과; 대기 시각과 이전 진행 보존 |
| `failed` | 비재시도 HTTP 실패 또는 유한 재시도 소진 |
| 상세 `parsed` | DOM 파싱 결과 저장; 필수 취득 조건/이미지/서비스 적합성 검증과 별개 |
| `image_validated` | 실제 디코딩과 크기 상한을 통과한 썸네일 원본 저장 |

차단 상태는 우회하지 않고 원인을 확인한다. 구조 변화가 확인되면 현 parser로 반복 실행하지
말고 parser 변경과 새 버전의 오프라인 검증을 진행한다. CLI는 차단·대기·실패를 nonzero로
종료하고 출력 경로·상태·원인을 JSON으로 알린다. 후보별 실패는 manifest에도 남는다.
현재는 상세·썸네일 후보 취득 실패 시에도 해당 실행을 멈춘다. 실패 후보를 건너뛰어 quota를
채우는 대체 후보 선택은 5단계에서 구현할 작업이다.

```text
run.json                       고정 plan, run ID, 시작 시각, parser/schema 및 네트워크 정책
manifest.json                  후보 관찰, 목록·상세 상태, 시도 이력, 대기 시각
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
처음 요청하지 않은 새 페이지를 재개 명령이 자동 탐색하지는 않는다.

완료 원본이나 존재하는 파싱 JSON의 해시가 다르면 `IntegrityError`로 거부하고 덮어쓰지 않는다.
원본이 손상되면 보존한 채 원인을 확인하고 새 run에서 다시 수집한다. 하나의 run에는 하나의
운영자 프로세스만 접근한다. 다중 writer 잠금과 모든 파일시스템의 전원 장애 내구성을 보장하지
않으며, 요청 중 강제 종료로 아직 응답이 저장되지 않았다면 해당 미완료 요청은 다시 필요할 수 있다.

Python API는 `CollectionRun.create/resume`, `fetch_list`, `fetch_detail`, `resume_pending`,
`snapshot`을 제공한다. API로 다음 페이지를 요청할 때도 저장 후보 처리를 우선한다.
Python API의 `resume_pending()`은 기존처럼 상세만 처리한다.
`resume_pending(include_images=True)`와 CLI는 검증된 썸네일까지 취득·재개한다.
quota·미달·검수 보고서는 5단계에서 연결한다.

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

4단계 산출물 스키마 버전은 `2`다. 이전 버전 `1` run은 조용히 변경하지 않고 새 실행 경로를
사용한다. 재개 시 이미지 정책도 동일해야 한다. 300×300 입력은 그대로 보존된다.
