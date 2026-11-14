# 만개의레시피 수집 계획 도구

현재 구현 범위는 **1–4단계의 계획 생성·파싱·원문/썸네일 저장·검증·재개**다. CLI import·도움말·`plan`은
네트워크, API 키, `tools/.env`, 서버 환경을 사용하지 않는다. `plan`은 JSON만 출력하며
출력 디렉터리·DB·이미지 파일을 생성하거나 수정하지 않는다.

## 설치 및 실행

저장소의 `tools/`에서 실행한다. 설치에는 패키지 저장소 접근이 필요할 수 있으나
설치 후 계획 생성과 테스트에는 레시피 사이트 접근이 필요하지 않다.

```powershell
uv sync --locked
uv run --locked python -m crawlers.tenkrecipes.cli --help
uv run --locked python -m crawlers.tenkrecipes.cli plan --output-dir ../data/tenkrecipes/runs/preview
```

`--output-dir`을 생략하면 저장소의 Git 제외 경로인
`data/tenkrecipes/runs/<unique-id>/`를 제안한다. 상대 경로는 현재 작업 디렉터리 기준이며
명시한 경로는 절대 경로로 출력한다. 서버·Android·기존 레시피 데이터·도구 소스 등
보호 대상 경로의 내부 또는 상위 경로와 기존 파일은 출력 대상으로 거부한다.
외부 출력 경로를 선택했다면 해당 생성물이 버전 관리에 포함되지 않도록 별도 관리한다.

아래는 문서 예제 검증용 형식이다. `{output_dir}`을 사용할 경로로 바꾼다.

```powershell
python -m crawlers.tenkrecipes.cli plan --output-dir {output_dir}
```

## 계획 계약

상황은 `초스피드`(`cat2=18`), 정렬은 사이트의 추천순(`order=reco`)이다.
추천순을 월간 순위로 해석하지 않으며, 초스피드를 특정 시간·인분 제한으로 바꾸지 않는다.

| 종류 | cat4 | 목표 |
|---|---|---:|
| 밑반찬 | 63 | 100 |
| 메인반찬 | 56 | 90 |
| 국/탕 | 54 | 60 |
| 찌개 | 55 | 30 |
| 면/만두 | 53 | 60 |
| 밥/죽/떡 | 52 | 100 |
| 퓨전 | 61 | 20 |
| 양식 | 65 | 20 |
| 샐러드 | 64 | 20 |
| **합계** | | **500** |

JSON은 `total`, `output_dir`, 순서 있는 `categories`를 포함한다.
각 category는 `name`, `cat4`, `quota`, 두 필터가 적용된 첫 페이지의 `list_url`을 갖는다.
Python API `crawlers.tenkrecipes.config.build_plan(output_dir=Path(...))`는
중첩 카테고리까지 읽기 전용인 계획을 반환한다. 서로 다른 계획 생성은 기존 계획과
기본 배분에 영향을 주지 않으며, 반환된 계획의 직접 수정은 허용하지 않는다.

## 중복과 후속 검수

- 같은 출처 레시피 ID의 반복 관찰은 한 레코드로 수집할 계획이다.
- ID가 다르면 이름·재료·조리법이 같아도 원본과 출처를 보존한다.
- **ID가 다른 500개는 서로 다른 요리 500개를 보장하지 않는다.** 서비스 반영 전에
  실질 중복 여부를 별도 검수해야 한다. 자동 의미 중복 제거는 이번 수집 범위 밖이다.
- 재료 수량 누락 등도 원문 보존 후 검수할 항목이다. 수집 완료가 서비스 적합성을 뜻하지 않는다.

`collect --live`는 지정 분류의 목록 한 페이지·후보 상세·검증된 원본 썸네일을 저장하고,
`resume --live`는 저장된 후보와 이전에 요청한 실패 목록을 재개한다.
후보 실패의 다음 후보 진행, 연속 네트워크 실패 3건 중단 및 이미지 정책 위반의 운영자 확인은
[오류·재개 안내](RUNS.md)를 따른다. 현재 run 스키마는 3이며 이전 run은 새 경로로 시작한다.
**500개 quota 자동 순회·검수 보고서는 아직 구현하지 않았다.**
실제 사이트 실행은 운영자의 별도 실행으로만 진행한다.
기존 서비스 CSV·DB·재료 ID·이미지·Android·API·AI 프롬프트에는 변경을 가하지 않는다.
서비스 데이터 변환·배포는 별도 작업이다.

## 로컬 HTML 파싱

저장된 UTF-8 상세 HTML을 읽고 JSON을 stdout으로 출력한다. BOM이 있는 UTF-8도 지원한다.
입력 파일을 수정하거나 이미지 URL에 접근하지 않고 출력 파일도 직접 생성하지 않는다.
목록 파싱은 Python API로 제공한다.

```powershell
uv run --locked python -m crawlers.tenkrecipes.cli parse --input source.html --source-url https://www.10000recipe.com/recipe/900001
```

```python
from crawlers.tenkrecipes.parsing import parse_list_page, parse_recipe

page = parse_list_page(list_html, source_url=list_url)
record = parse_recipe(detail_html, source_url=recipe_url)
```

DOM을 기준으로 재료·수량·설명·단계·팁을 보존하며 JSON-LD는 설명·작성자·날짜 등
메타데이터를 보완한다. 제목만 엔티티·Unicode NFC·공백 정규화 후 비교한다.
차이가 있어도 DOM 제목을 사용하고 양쪽 제목·출처 URL을 finding으로 남긴다.
수량 보완·단위 환산·재료/단계 비교·도구 추론은 하지 않는다.
필터 소실·구조 변경은 `ParseError`, CLI 입력/파싱 오류는 nonzero 종료로 표시한다.

[출력 스키마와 오류 계약](SCHEMA.md)을 참고한다. 합성 fixture에 대한 검증이며
모든 실제 페이지와의 호환성을 보장하지 않는다. `parse`는 입력을 보존하며,
수집 명령의 원본 HTML 저장은 collection 저장 계층이 담당한다.

## 원문 수집과 재개

`--live` 없이 collect/resume을 실행하면 요청·디렉터리 생성 전에 거부한다.
source-use-review 파일이나 옵션은 요구하지 않는다. 설치 후 네트워크 실행은 명시적인
live 명령에서만 일어난다. [저장·재개 운영 안내](RUNS.md)에 실행 전 확인 사항, 명령,
산출물, 재시도·대기·차단 상태 및 복구 한계를 정리했다. 이 구현 과정에서는 실수집하지 않았다.

## 검사

`tools/`에서 기존 Pixabay 테스트와 신규 계약 테스트를 함께 실행한다.

```powershell
uv run --locked pytest --collect-only -q
uv run --locked pytest
uv run --locked ruff check crawlers
uv run --locked ruff format --check crawlers
```

신규 테스트는 네트워크와 운영 데이터 접근을 차단한 환경에서 CLI·계획·파싱을 검증한다.
기존 Pixabay 모듈의 bare import와 충돌하지 않도록 신규 코드에서는 패키지 상대 import를 사용한다.
