# 레시피 이미지 후보 선별 도구 스펙

Pixabay API로 레시피별 이미지 **후보**를 뽑아 HTML 시트로 보여주고, 사람이 고른 결과를 기록한 뒤, 사람이 내려받은 파일을 앱용 WebP로 가공하는 CLI 도구.

## 1. 목표와 범위

- 레시피 약 500개를 50개 단위 배치로 처리한다. (경로: C:\Users\ayoon\Documents\GitHub\swpp-2026-project-team-15\data\recipes\Recipe.csv)
- 배치마다 레시피당 후보 이미지 5개를 검색해 **검토용 HTML 시트**를 생성한다.
- 사람이 시트에서 이미지를 고르고, 선택 결과를 CSV로 내보낸다.
- 사람이 Pixabay 페이지에서 직접 내려받은 원본을 앱용 WebP(3종 크기)로 변환한다.
- 출처(촬영자, 페이지 URL) 기록을 보관해 앱의 "이미지 출처" 화면에 쓸 수 있게 한다.

### 하지 않는 것 (중요)

Pixabay API 문서는 "systematic mass downloads"를 허용하지 않고, 이미지 URL의 영구 핫링킹도 금지한다. 따라서 이 도구는 다음을 **절대 구현하지 않는다.**

- Pixabay 이미지 파일(`webformatURL`, `largeImageURL` 등)을 스크립트로 자동 다운로드하는 기능. 검색 JSON 호출만 한다.
- Pixabay URL을 DB나 앱 데이터에 영구 저장하는 기능.
- 반환된 URL을 임시 표시(시트 썸네일) 외의 용도로 사용하는 기능.
- 다운로드는 항상 사람이 `pageURL`을 열어 직접 수행한다.

## 2. 기술 스택

- Python 3.11+
- `requests`, `Pillow`, `typer`(또는 `argparse`)
- 외부 서비스는 Pixabay API 하나뿐
- API 키는 환경변수 `PIXABAY_KEY`로만 받는다. 코드, 설정 파일, 시트 HTML에 키를 남기지 않는다.

## 3. 디렉터리 구조

```
recipe-images/
├── SPEC.md
├── recipes.json            # 입력 (사람이 관리)
├── pyproject.toml
├── src/recipe_images/
│   ├── cli.py              # 명령어 진입점
│   ├── search.py           # Pixabay 검색 + 캐시 + 속도 제한
│   ├── sheet.py            # HTML 시트 생성
│   ├── process.py          # 다운로드된 원본 → WebP 변환
│   └── models.py           # 데이터 클래스
├── cache/                  # 검색 결과 JSON 캐시 (gitignore)
├── sheets/                 # sheet_01.html ... (gitignore)
├── selections/             # selected_01.csv ... 사람이 내보낸 선택 결과
├── downloads/              # 사람이 직접 받은 원본 {recipe_id}.{ext}
├── output/
│   ├── images/             # {recipe_id}_thumb.webp, _list.webp, _detail.webp
│   └── attribution.json    # 출처 정보
└── tests/
```

`.gitignore`에 `cache/`, `sheets/`, `downloads/`, `.env`를 포함한다.

## 4. 입력 형식

`recipes.json`

```json
[
  { "id": 1, "name_ko": "김치찌개", "query": "김치찌개" },
  { "id": 2, "name_ko": "부침개", "query": "부침개" }
]
```

- `id`: 정수, 고유값. 모든 파일명과 CSV의 기준 키.
- `query`: 한국어 검색어(100자 이하). 기본은 레시피명이며, 사람이 한국어 키워드를 고치면 재검색에 반영된다.
- 검증: `id` 중복, `query` 누락·100자 초과 시 명확한 오류 메시지와 함께 종료한다.

## 5. CLI 명령어

```
recipe-images search  --batch N [--force]
recipe-images sheet   --batch N
recipe-images process [--selection selections/selected_01.csv ...]
recipe-images status
```

배치 N은 1부터 시작하며 `recipes.json`의 `(N-1)*50 ~ N*50-1` 구간이다. `--batch-size`로 크기를 바꿀 수 있고 기본값은 50.

### 5.1 `search`

배치의 각 레시피에 대해 Pixabay 검색을 호출하고 결과를 캐시한다.

요청 파라미터 (고정값):

| 파라미터 | 값 |
|---|---|
| `category` | `food` |
| `image_type` | `photo` |
| `per_page` | `5` |
| `safesearch` | `true` |
| `min_width` | `800` |
| `lang` | `ko` |

동작 규칙:

- **캐시:** `cache/{id}.json`에 `{ "fetched_at": ISO8601, "query": "...", "lang": "ko", "hits": [...] }` 저장. 같은 레시피의 캐시가 24시간 이내이고 `query`와 `lang`이 동일하면 API를 호출하지 않는다. `--force`는 이 규칙을 무시하되, 24시간 이내 재호출이면 경고를 출력하고 사용자 확인을 받는다.
- **속도 제한:** 기본 100요청/60초. 호출 사이에 최소 1초 대기한다. 응답 헤더 `X-RateLimit-Remaining`이 5 이하이면 `X-RateLimit-Reset`초만큼 대기한다.
- **429 처리:** `X-RateLimit-Reset`만큼 대기 후 최대 3회 재시도, 이후 해당 레시피를 실패로 기록하고 계속 진행한다.
- **그 외 오류:** 타임아웃 10초, 네트워크 오류는 2회 재시도. 실패한 레시피는 종료 시 목록으로 출력한다.
- 결과가 0건이면 캐시에 빈 `hits`로 저장하고 시트에 "후보 없음"으로 표시한다.
- 캐시에는 시트와 출처 기록에 필요한 필드만 보관한다: `id`, `pageURL`, `webformatURL`, `tags`, `user`, `user_id`, `imageWidth`, `imageHeight`.

### 5.2 `sheet`

배치의 캐시를 읽어 `sheets/sheet_{NN}.html`을 생성한다. API는 호출하지 않는다.

시트 요구사항:

- 자체 완결 HTML 한 파일(CSS, JS 인라인). 외부 라이브러리 없음.
- 상단에 배치 번호, 생성 시각, 그리고 **"webformatURL은 24시간 후 만료됩니다. 생성 시각으로부터 24시간 안에 검토하세요"** 경고를 표시한다.
- 상단 또는 하단에 "Images from Pixabay" 문구와 `https://pixabay.com` 링크를 표시한다.
- 레시피별 섹션: `{id}. {name_ko} ({query})` 제목, 그 아래 후보 카드가 가로로 나열된다.
- 후보 카드: 썸네일(`webformatURL`, 너비 220px, `loading="lazy"`), 라디오 버튼(레시피당 1개 선택, "선택 안 함" 포함), Pixabay ID, 촬영자, 태그, 해상도, 그리고 `pageURL`로 가는 "Pixabay에서 열기" 링크(`target="_blank" rel="noopener"`).
- "후보 없음" 레시피는 안내 문구와 함께 라디오가 "선택 안 함"만 있다.
- 하단 고정 바: 선택 개수 표시와 **"CSV 내보내기"** 버튼. 클릭 시 브라우저에서 `selected_{NN}.csv`를 생성해 다운로드한다 (서버 없이 JS Blob 사용).
- 선택 상태는 `localStorage`에 저장해 새로고침해도 유지한다.
- 반응형 레이아웃, 다크 모드 대응은 필수가 아니다.

`selected_{NN}.csv` 형식 (UTF-8, 헤더 포함):

```
recipe_id,pixabay_id,user,user_id,page_url,tags
1,195893,Josch13,48777,https://pixabay.com/...,"blossom, bloom"
```

선택 안 함으로 둔 레시피는 행을 만들지 않는다.

### 5.3 `process`

사람이 `downloads/`에 받아둔 원본을 앱용으로 가공한다. 이 단계는 Pixabay와 통신하지 않는다.

입력:

- `downloads/{recipe_id}.{jpg|jpeg|png|webp}` 형식의 파일명 규칙을 따른다. (사용자가 내려받은 뒤 파일명을 바꿔야 한다.)
- `selections/*.csv`: 선택 결과. `--selection`을 생략하면 `selections/` 안 전체를 합친다. 같은 `recipe_id`가 여러 번 나오면 마지막 파일 기준.

처리:

1. 선택 CSV에 있는 `recipe_id`마다 `downloads/`에서 원본을 찾는다. 없으면 경고 후 건너뛴다.
2. EXIF 회전 보정(`ImageOps.exif_transpose`) 후 RGB로 변환한다.
3. 긴 변이 아니라 **너비 기준**으로 리사이즈한다 (원본보다 크게 키우지 않는다):

| 이름 | 너비 | 용도 | WebP quality |
|---|---|---|---|
| `thumb` | 300 | 썸네일 | 75 |
| `list` | 600 | 목록 | 78 |
| `detail` | 1200 | 상세 | 80 |

4. `output/images/{recipe_id}_{name}.webp`로 저장한다. 이미 존재하고 원본보다 최신이면 건너뛴다 (`--force`로 덮어쓰기).
5. `output/attribution.json`을 갱신한다:

```json
{
  "1": {
    "pixabay_id": 195893,
    "user": "Josch13",
    "user_id": 48777,
    "page_url": "https://pixabay.com/...",
    "source": "Pixabay"
  }
}
```

6. 각 이미지의 BlurHash 또는 ThumbHash를 계산해 `output/placeholders.json`(`{ "1": "<hash>" }`)에 저장한다. 라이브러리(`blurhash-python` 등)는 선택 의존성이며, 설치되어 있지 않으면 이 단계를 건너뛰고 안내만 출력한다.

종료 시 요약을 출력한다: 처리 N건, 건너뜀 N건, 원본 없음 목록, 총 출력 용량.

### 5.4 `status`

전체 진행 현황 표를 출력한다.

```
batch  searched  selected  downloaded  processed
 01     50/50     48/50     40/48       40/40
 02     50/50     --        --          --
```

- searched: `cache/`에 유효한 파일이 있는 레시피 수
- selected: 선택 CSV에 있는 수
- downloaded: `downloads/`에 원본이 있는 수
- processed: `output/images/`에 3종이 모두 있는 수

선택은 됐지만 원본이 없는 `recipe_id`, 후보가 없는 `recipe_id`를 마지막에 목록으로 출력한다 (후보 없는 항목은 AI 생성이나 직접 촬영으로 보완 대상).

## 6. 비기능 요구사항

- **멱등성:** 같은 명령을 다시 실행해도 안전해야 한다. 캐시, 변환 결과를 불필요하게 다시 만들지 않는다.
- **로깅:** 표준 출력에 진행률(`[12/50] 김치찌개 ...`)과 요약을 출력한다. API 키는 로그에 절대 출력하지 않는다.
- **오류 격리:** 레시피 하나의 실패가 배치 전체를 중단시키지 않는다.
- **테스트:** `pytest`. Pixabay 호출은 모킹한다. 최소한 다음을 커버한다.
  - 캐시 적중/만료 판정 (24시간 경계)
  - 429 재시도와 대기 로직
  - `recipes.json` 검증 (중복 id, 긴 query)
  - 시트 HTML에 키가 포함되지 않음
  - `process`의 리사이즈 (업스케일 없음, 너비 기준), 파일명 규칙, 원본 누락 처리
- **코드 스타일:** 타입 힌트, `ruff` 통과.

## 7. 구현 순서 (권장)

1. 프로젝트 골격, `models.py`, `recipes.json` 로더와 검증
2. `search.py` (캐시, 속도 제한, 재시도) + 테스트
3. `sheet.py` + 샘플 캐시로 시트 수동 확인
4. `process.py` + 테스트
5. `status`, 마무리, README

각 단계가 끝날 때마다 테스트를 돌리고 커밋한다.
작업 과정을 codex_note.md에 모두 기록한다. (이 스펙 구현 이전에 기록된 정보가 있다면 덮어쓰기 한다.)

## 8. 완료 기준

- [ ] `search --batch 1` 실행 시 50건의 캐시가 생기고, 즉시 재실행하면 API 호출이 0회다.
- [ ] 생성된 시트에서 라디오 선택, CSV 내보내기, 새로고침 후 선택 유지가 동작한다.
- [ ] 시트와 코드베이스 어디에도 API 키가 남지 않는다.
- [ ] Pixabay 이미지 파일을 내려받는 코드 경로가 존재하지 않는다 (검색 JSON 호출만 있음).
- [ ] `process`가 `downloads/`의 파일로부터 3종 WebP와 `attribution.json`을 생성한다.
- [ ] `status`가 위 형식으로 진행 현황과 누락 목록을 출력한다.
- [ ] `pytest`, `ruff`가 통과한다.

## 9. 참고: Pixabay API 요약

- 엔드포인트: `GET https://pixabay.com/api/`
- 속도 제한: 키당 100요청/60초 (헤더 `X-RateLimit-Limit`, `-Remaining`, `-Reset`), 초과 시 HTTP 429
- 요청은 24시간 캐시해야 한다.
- 쿼리당 최대 500건까지 접근 가능 (`totalHits`)
- `webformatURL`(최대 640px)은 24시간만 유효하다. `largeImageURL`은 최대 1280px이다.
- `fullHDURL`, `imageURL`(원본)은 풀 API 접근 승인이 있는 계정에서만 제공된다.
- 영구 핫링킹 금지, 대량 다운로드 금지. 검색 결과 표시 시 출처(Pixabay) 표기를 요청한다.
- 공식 문서: https://pixabay.com/api/docs/
