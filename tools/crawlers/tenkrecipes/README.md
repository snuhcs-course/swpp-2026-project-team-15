# 만개의레시피 수집 계획 도구

현재 구현 범위는 **1단계의 오프라인 계획 생성**이다. CLI import·도움말·`plan`은
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

목록·상세 파싱, 원문·썸네일 취득, 진행 저장·재개 및 검수 보고서는 아직 구현하지 않았다.
`collect` 등 live 명령도 제공하지 않는다. 실제 수집은 후속 구현과 별도 실행 요청 후 진행한다.
기존 서비스 CSV·DB·재료 ID·이미지·Android·API·AI 프롬프트에는 변경을 가하지 않는다.
서비스 데이터 변환·배포는 별도 작업이다.

## 검사

`tools/`에서 기존 Pixabay 테스트와 신규 계약 테스트를 함께 실행한다.

```powershell
uv run --locked pytest --collect-only -q
uv run --locked pytest
uv run --locked ruff check crawlers
uv run --locked ruff format --check crawlers
```

신규 테스트는 네트워크와 운영 데이터 접근을 차단한 환경에서 CLI·계획을 검증한다.
기존 Pixabay 모듈의 bare import와 충돌하지 않도록 신규 코드에서는 패키지 상대 import를 사용한다.
