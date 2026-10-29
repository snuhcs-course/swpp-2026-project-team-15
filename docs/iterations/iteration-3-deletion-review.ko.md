# 첫 확인 단계: 냉장고 재료 삭제

현재 단계는 삭제 기능의 로컬 구현·자동 검증입니다. 아이콘, 부족 재료 표시, 레시피 사진은 다음 단계입니다. 사용자의 직접 확인과 수동 코드는 아직 기록하지 않았습니다.

## Android Studio에서 열기

1. 이 작업 폴더의 `android`를 Open 합니다. 예전 `android/MyLittleChef` 폴더와 구분해 주세요.
2. Gradle Sync 후 Build Variants에서 app의 `cloudTest`를 선택합니다.
3. 휴대폰 USB 디버깅을 허용하고 실행 기기로 선택합니다. `MyLittleChef Cloud Test` 앱을 실행합니다.
4. 온보딩을 마치고 직접 입력으로 두부·계란·마늘·다진마늘을 등록합니다.

일반 실행의 서버 주소는 최신 main의 Gradle 기본값을 따릅니다. 자동 테스트 APK는 로컬 주소를 지정해 빌드했습니다. 로컬 서버를 사용하려면 Android README의 설치 방법에 따라 `serverBaseUrl=http://127.0.0.1:8000/`을 지정하고 `adb reverse tcp:8000 tcp:8000`을 설정합니다. 삭제와 저장 자체는 서버 없이 확인할 수 있습니다. 실제 레시피 갱신 확인에는 실행 중인 서버가 필요합니다.

## 직접 확인할 순서

| 조작 | 예상 결과 | 본인 확인 |
| --- | --- | --- |
| 두부를 길게 누름 | '두부 삭제' 확인 창 | 미확인 |
| 취소 | 두부가 그대로 남음 | 미확인 |
| 관리 → 마늘의 삭제 버튼 → 삭제 | 마늘만 사라지고 다진마늘은 남음 | 미확인 |
| 앱을 완전히 종료하고 다시 실행 | 삭제한 마늘이 다시 나타나지 않음 | 미확인 |
| 두부 삭제 후 레시피 탭으로 이동 | 서버에 두부를 제외한 재고로 다시 요청 | 미확인 |
| 마지막 재료까지 삭제 | 빈 냉장고 안내와 재료 추가 버튼 | 미확인 |

소금·설탕 등은 현재 서버가 보유한 것으로 가정하므로, 추천 변화는 두부·계란으로 확인합니다. 저장 실패와 지연 응답은 자동 테스트의 제어된 환경에서 검증합니다.

## 코드에서 읽을 부분

1. [FridgeViewModel.removeIngredient](../../android/app/src/main/java/com/example/mylittlechef/viewmodel/FridgeViewModel.kt): 선택한 재료가 있는지 확인 → 중복 작업 차단 → 저장 요청 → 성공한 저장소 Flow가 화면 변경 → 실패 시 재료 유지와 오류 안내.
2. [FridgeScreen](../../android/app/src/main/java/com/example/mylittlechef/ui/fridge/FridgeScreen.kt): 관리 모드와 길게 누르기가 같은 pendingName에 연결되고, 확인 창에서만 removeIngredient를 호출합니다. 취소는 pendingName만 비웁니다.
3. [RecipeViewModel.refresh](../../android/app/src/main/java/com/example/mylittlechef/viewmodel/RecipeViewModel.kt): 매 요청에 번호를 붙이고, 현재 요청 번호와 다른 늦은 응답은 화면에 반영하지 않습니다.

먼저 코드를 보고 '취소하면 저장 함수가 호출될까?', '마늘을 지우면 다진마늘도 지워질까?', '저장 실패 시 재료가 사라질까?'의 예상 답을 적어 주세요. 앱 결과와 비교한 실제 관찰만 AI 기록에 추가합니다. 이해한 뒤 개선할 점이 보일 때 직접 고치며, 보고서를 위해 일부러 수정을 만들 필요는 없습니다.

## 실제 자동 검증 결과

2026-10-28 최종 결과: Android JVM 28개, 에뮬레이터 UI 5개 통과. 린트·커버리지 보고서·debug/cloudTest 빌드 성공. 실제 명령과 제약은 AI work log에 기록했습니다. 자동 캡처는 에뮬레이터 테스트 화면이며 사용자의 수동 시연으로 표현하지 않습니다.

Windows에서는 기존 보호 파일 검사 스크립트가 CRLF checkout 때문에 raw 해시 비교에 실패했습니다. 29개 보호 파일을 Git 원본 및 manifest와 비교한 결과 내용 변경은 없었고 줄바꿈만 달랐습니다. 보호 파일과 manifest는 수정하지 않았습니다.
