# AI Collaboration Report – Iteration 1

Tools used: Claude (claude.ai 채팅, 모델: Sonnet 5.5)


## 1. Where AI Was Used

- **AI가 초안 작성 후 작업자가 가져와 수정**
  - 네비게이션: `navigation/Routes.kt`, `AppNavHost.kt`, `MainScreen.kt` (하단 탭, 탭용 NavHost, 레시피 중첩 그래프)
  - 온보딩: `ui/onboarding/OnboardingScreen.kt` (단계 전환, 진행 바, 뒤로가기/건너뛰기/다음)
  - 냉장고 탭: `ui/fridge/FridgeScreen.kt`, `components/FridgeShelves.kt`, `IngredientItem.kt`, `model/Ingredient.kt`
  - 재료 추가 흐름: `ui/fridge/add/CaptureScreen.kt`, `CameraPreview.kt`(CameraX), `AnalyzeScreen.kt`, `ManualAddScreen.kt`, `components/AddFlowLayout.kt`, `EditableIngredientList.kt`, `IngredientRow.kt`, `ui/components/DashedButton.kt`
  - `ui/components/AppText.kt`: AI의 `<hl>` 태그 파싱 구조 → 작업자가 `<color=#RRGGBB>`로 변경
- **AI는 리뷰/조언만**: `ui/recipe/RecipeScreen.kt`, `RecipeDetailScreen.kt`(작업자가 직접 작성), 폴더/패키지 구조, Screen/ViewModel 분리, Figma → Compose 변환 방법
- **AI 미사용**: `UserViewModel`, `FridgeViewModel`, `Preset`/`Recipe` 모델, 테마 색상, 버튼 컴포넌트(`NormalButton` 등)

## 2. Prompt History

[Ahyoon, 10-4] "안드로이드 스튜디오로 작동하는 클라 앱 프로그램 프론트엔드 작업 할 거야. 피그마로 UI 작업은 끝났어. 일단 하나의 화면을 안드로이드 스튜디오에서 어떻게 정의하는지 알려줘."

[Ahyoon, 10-4] "일단 온보딩 스크린 먼저 구현해보자. 뒤로 가기 버튼, 다음 버튼, 건너뛰기 버튼, 프로그레스 바, 실질적 내용으로 구성돼. 실질적 내용은 타이틀 텍스트, 서브 텍스트, 그리고 입력칸이나 선택 창 등... 으로 되어 있음." (줄바꿈 생략)

[Ahyoon, 10-4] "이제 fridge 탭 쪽을 구현하려고 하는데, 뭐부터 하면 될지 알려줘" (Figma 스크린샷 첨부)

[Ahoon, 10-4] "이제 CaptureScreen, AnalyzeScreen, ManualAddScreen을 만들어보자."

[Ahyoon, 10-4] "카메라 X 적용해줘"

[Ahyoon, 10-4] "텍스트 중간의 특정 글자에만 색이 넣고 싶으면 어떻게 해" → "그냥 텍스트에 태그로 받아서 AppText가 파싱하는 방식이면 안되냐"

[Ahyoon, 10-4] "MainScreen 유지하고, detail 클릭하면 디테일 뷰로 넘어가게 하고 싶어" (`RecipeScreen.kt`, `RecipeDetailScreen.kt` 첨부)

## 3. What AI Did Well

- **Figma 스크린샷 분해**: 6개 프레임을 4개 화면으로 정리하고(분석 중/실패/성공은 한 화면의 3가지 상태), 겹치는 부품을 찾아냈다. 이 분석을 바탕으로 재료 추가 흐름 전체를 만들었다. 절약 시간 약 3시간.
- **재사용 설계**: `EditableIngredientList`와 `IngredientEditorState`로 분석 성공 화면과 직접 입력 화면이 같은 목록 UI를 공유해 중복을 없앴다.
- **후속 요청 반영**: "냉장고 카드가 재료 수에 따라 세로로 길어져야 한다"는 요청에 카드를 스크롤 컨테이너 안으로 옮기고 `heightIn(min = …)`로 해결했다.
- **실행 전 버그 발견**: `AppText.kt`의 `Color(….toULong())` 오류와 Recipe 코드의 컴파일 에러(`onRecipeCardClick` 미선언), 레이아웃 문제(`weight`, `clip` 순서)를 리뷰에서 지적했다.

## 4. Hallucinations / Errors

- **저장 불가능한 타입**: 온보딩 초안이 `rememberSaveable`에 `Set<String>`을 써서 화면 회전 시 크래시 위험이 있었고, `statusBarsPadding` import도 빠져 있었다. AI가 다음 답변에서 스스로 정정했다. 
- **의존성 호환 미확인**: CameraX, Coil, lifecycle 버전 추가를 안내한 뒤 `kotlin-stdlib 2.4.0`과 컴파일러 2.2의 메타데이터 불일치로 빌드가 깨졌다(원인 라이브러리는 추정). Gradle 빌드에서 발견했고 Kotlin을 2.4.0으로 올려 해결.
- **추측성 진단**: `NavigationBarItem` unresolved와 `ComposableFunction0` 에러에서 원인 후보를 나열했을 뿐 확정하지 못했다. 
- **검증되지 않은 코드**: AI는 빌드해 보지 못했고, 테마 이름(`MyLittleChefTheme`), 아이콘 리소스(`ic_gallery` 등), `UserViewModel`/`Recipe.id` 타입을 가정해서 작성했다.

## 5. Prompt Revisions

- **Before**: "텍스트 중간의 특정 글자에만 색이 넣고 싶으면 어떻게 해" → "…'특정 부분만 색이 다른 텍스트'가 파라미터로 들어가서 반영될 수 있게 해줘" (`highlights` 목록 파라미터 방식)
- **After**: "그냥 텍스트에 태그로 받아서 AppText가 파싱하는 방식이면 안되냐"
- **Why it worked**: 강조 위치를 문장 안에 직접 표시하니 같은 단어가 반복될 때의 모호함이 사라졌고, 문장을 앞/뒤로 쪼개지 않아도 됐다.
- **보조 사례**: "진짜 그게 최선?"이라는 짧은 반문이 단일 답변을 방식별 비교(직접 작성/플러그인/AI 생성)로 바꿨다.

## 6. Manual Fixes and Why

- **`AppText.kt`**: AI의 `<hl>` 방식 대신 `<color=#RRGGBB>` 태그로 직접 변경했다. 이유: 텍스트 파라미터에 색상 정보를 함께 넣을 수 있게 하기 위함. 이 과정에서 생긴 `Color(ULong)` 버그는 AI 리뷰로 발견했다.
- **Recipe 화면 전체**: `RecipeScreen.kt`, `RecipeDetailScreen.kt`를 직접 작성했다. 이유: 토큰 부족.
- **버튼 컴포넌트와 ViewModel**: 직접 작성했다. 이유: 토큰 부족.
- **AI 초안의 임시 값**(색상, 간격, 크기): Figma 값으로 직접 교체.

## 7. Takeaway for Iteration 2

- 의존성은 한 번에 하나씩 추가하고, Kotlin/AGP 호환을 확인한 뒤 Sync한다.
- ViewModel과 모델 파일을 먼저 붙여넣고 연결 코드를 요청한다.