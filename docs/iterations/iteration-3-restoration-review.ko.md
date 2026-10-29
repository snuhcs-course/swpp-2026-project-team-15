# 기존 기능 통합 — 직접 확인 안내

2026-10-29. 로컬 브랜치 `frontend/iter3-inventory-and-images`에서 작업했습니다. 클라우드 서버 배포·GitHub 업로드·PR은 하지 않았습니다. 실제 사용자의 화면 확인과 코드 검토는 아직 남아 있습니다.

## 무엇이 다시 연결됐는가

| 위치 | 확인할 기능 |
| --- | --- |
| 첫 실행 온보딩 | 별명 → 조리도구 → 알레르기 → 기본 재료·조미료 20종 체크 → 시작 |
| 내 정보 | 기본 재료·조미료 항목에서 재선택 및 저장 |
| 냉장고 우상단 | 추천 버튼으로 식재료 추가 추천 열기; 관리 버튼·길게 누르기 삭제 유지 |
| 직접 입력 | 이름 일부를 입력하면 등록된 재료명 최대 5개 표시, 선택해 확정 |
| 사진 인식 결과 편집 | 인식 결과 이름을 고칠 때 같은 자동완성 사용 |
| 레시피 탭 | 현재 재고로 기존 서버 레시피 목록 조회, 기존 정렬 유지 |

기본 재료 체크는 기존 로컬 기능의 12개 조미료+8개 기본 식재료입니다. 앞으로 추가할 아이콘 종류와는 별개의 목록입니다. 체크 해제는 이 20종에만 적용하며 그 외 등록 재료는 유지합니다.

## 지금 화면 확인

Android Studio에서 이 작업 폴더의 `android/`를 열고 Running Devices의 `Medium Phone`을 선택하세요. 별도 패키지 **MyLittleChef Cloud Test**를 사용하며 기존 일반 앱과 구분됩니다.

이 로컬 테스트 APK는 `http://127.0.0.1:8000/`에 연결합니다. 이번에 추가한 API는 클라우드 서버에 배포하지 않았으므로, 클라우드 기본 주소로 빌드하면 자동완성·식재료 추천을 사용할 수 있다고 가정하면 안 됩니다.

직접 확인할 순서:

1. 온보딩에서 소금·설탕·밥·계란 등을 고르고 냉장고에 나타나는지 확인합니다.
2. 내 정보 → 기본 재료·조미료에서 일부를 해제하고 다른 항목을 선택해 저장합니다. 앱을 다시 실행해 선택과 재고가 유지되는지 확인합니다.
3. 직접 입력으로 목록 밖 재료(예: 생강)를 등록하고, 기본 재료 체크를 수정해도 그 재료가 보존되는지 확인합니다.
4. 직접 입력에서 `양`을 입력하고 `양파` 자동완성을 선택합니다. 사진 인식 결과 편집에서도 이름 수정 시 같은 방식이 동작합니다.
5. 냉장고의 추천을 열어 ‘추가하면 바로 만들 수 있는 요리’와 ‘이 재료가 들어가는 전체 레시피’를 구분해서 확인합니다.
6. 관리 모드 또는 길게 누르기로 두부 등을 지우고, 취소와 확인이 각각 유지/삭제로 동작하는지 확인합니다.
7. 레시피 탭에서 현재 재고로 목록이 갱신되는지 확인하고 정렬 세 종류도 확인합니다.

현재 서버의 기본 조미료 보유 가정은 유지했습니다. 따라서 소금 등을 체크 해제해도 서버가 부족 재료로 계산하지 않을 수 있습니다. 식재료 추천 수에는 조리도구·알레르기 필터와 AI 레시피 수정이 반영되지 않습니다. 음식 사진 인식의 이번 자동 검증은 mock 응답이며 실제 인식 품질을 증명하지 않습니다.

## 다음 실행 때 서버·앱 준비

PowerShell 터미널 1에서:

```powershell
$projectRoot = "C:/Users/geulc/.codex/worktrees/iter3-inventory-and-images/swpp-2026-project-team-15"
Set-Location "$projectRoot/server"
$env:VISION_PROVIDER = "mock"
$env:REVISION_PROVIDER = "mock"
$env:DATABASE_URL = ""
$env:RECIPE_DB_PATH = "$projectRoot/.superpowers/restoration-recipes.sqlite3"
./.venv/Scripts/python.exe -m uvicorn app.main:create_app_from_env --factory --host 127.0.0.1 --port 8000
```

DB와 가상환경은 이 컴퓨터에서 준비한 로컬 파일이며 Git에는 포함되지 않습니다. 포트 8000 서버가 이미 실행 중이면 서버를 중복 실행하지 않습니다.

터미널 2에서 (에뮬레이터를 켠 상태):

```powershell
$projectRoot = "C:/Users/geulc/.codex/worktrees/iter3-inventory-and-images/swpp-2026-project-team-15"
$adb = "C:/Users/geulc/AppData/Local/Android/Sdk/platform-tools/adb.exe"
$env:JAVA_HOME = "C:/Program Files/Android/Android Studio/jbr"
$env:ANDROID_HOME = "C:/Users/geulc/AppData/Local/Android/Sdk"
& $adb -s emulator-5554 reverse tcp:8000 tcp:8000
Set-Location "$projectRoot/android"
./gradlew.bat :app:assembleCloudTest -PserverBaseUrl=http://127.0.0.1:8000/ --offline --console=plain
& $adb -s emulator-5554 install -r app/build/outputs/apk/cloudTest/app-cloudTest.apk
& $adb -s emulator-5554 shell am start -n com.example.mylittlechef.cloudtest/com.example.mylittlechef.MainActivity
```

휴대폰에서는 `adb devices`에 표시된 휴대폰 serial로 `emulator-5554`를 바꿉니다. 실제 휴대폰에서는 아직 이번 버전을 검증하지 않았습니다. Android Studio에서 별도 설정 없이 재빌드하면 기본 서버 주소가 적용될 수 있으므로 위 명령으로 로컬 주소를 지정합니다.

## 코드를 이해할 순서

- `model/Preset.kt`: 체크할 기본 재료 목록입니다.
- `ui/onboarding/OnboardingScreen.kt`, `ui/profile/EditPantryScreen.kt`: 선택과 저장 완료 후 화면 이동을 연결합니다. 저장 중에는 뒤로 가기를 막아 완료 콜백이 다른 화면을 닫지 않도록 합니다.
- `viewmodel/FridgeViewModel.kt`의 `updatePantryItems`: 체크 목록 외 재료를 보존하고 저장 결과를 처리합니다.
- `data/local/FridgeRepository.kt`의 `replaceSelection`: DataStore의 한 트랜잭션으로 기본 재료 선택을 교체합니다.
- `viewmodel/IngredientCatalogViewModel.kt`, `ui/fridge/components/IngredientComponent.kt`: 서버 재료 목록을 받아 입력 문자열에 맞는 후보를 보여줍니다.
- `viewmodel/IngredientSuggestionViewModel.kt`: 현재 재고를 서버에 전달하고 늦은 이전 응답을 무시합니다.
- `server/app/recipes/service.py`의 `ingredient_suggestions`: 새로 완성되는 요리 수 → 전체 포함 요리 수 → 이름 순으로 후보를 정렬합니다. 대파/다진파의 방향성을 보존합니다.

사용자 확인 여부: 미확인. 직접 관찰한 결과와 직접 수정한 코드만 이후 AI 협업 보고서에 추가합니다.

## 자동 검증 기록

- Android JVM 34개 통과. 에뮬레이터 UI 14개 통과.
- 실제 Android Retrofit → 로컬 서버 통합 테스트 1개 통과: 재료 목록·식재료 추천·레시피·mock 사진 업로드의 네 API 확인.
- 레시피 서버 테스트 84개 통과(새 대파/다진파 회귀 포함).
- 이전 전체 서버 실행은 196 passed, 1 skipped, 106 subtests passed였습니다. 이후 회귀 1개를 추가한 전체 실행은 195 passed, 2 failed, 1 skipped였습니다. 두 실패는 Windows 파일 교체 PermissionError와 셸 실행 10초 TimeoutExpired였으며, 같은 테스트를 변경 없이 개별 재실행해 2개 모두 통과했습니다. 최신 전체 실행이 단번에 모두 통과했다고 기록하지 않습니다.
- 린트와 앱 빌드는 실제 완료 로그를 기준으로 확인합니다. 로그는 Git에서 제외되는 `.superpowers/restoration-*.log`에 있습니다.
- 소스 전용 독립 AI 리뷰에서 발견한 두 문제(준비 형태의 추천 계산, 저장 중 화면 이동)는 회귀 테스트로 재현 후 수정했습니다. 이는 사용자의 수동 코드 수정이나 GitHub PR 리뷰로 간주하지 않습니다.

최종 확인: 저장 중 화면 이동 수정 후 JVM 34개와 lintDebug가 다시 통과했습니다. 테스트 에뮬레이터에 로컬 주소 APK를 설치·실행했으며, 로컬 mock 서버를 실행해 두었습니다. 코드·기록은 로컬 커밋으로 저장하며 GitHub에는 올리지 않습니다.
