# Iteration 2 Prompt Log — Contributor Wording

Local unpublished draft, updated 2026-10-20. The original entries below are preserved verbatim; historical model names are contributor-reported. This log covers Jaehyuk only, pending team consolidation.

## Jaehyuk Choi

## 2. Prompt History

Claude Code (Opus 5.5), 2026-10-11 to 2026-10-14.

- 10-11: “준비된 readme.md 기반으로 내용 파악”
- 10-11: “아니 모든 작업은 일단 llm wiki 완성 및 정합성 검토한 다음 나에게 허락 받고 해”
- 10-11: “ㅇㅇ 데이터는 로컬용이니 mock이되, 백엔드에서 안드로이드 FE까지 데이터가 연결되도록 알아서 잘 하셈. Co-Authored-By: Claude 표기는 강의자료에 따른 것인가? 애당초 너 로컬 llm wiki 아직 작성 안했지.”
- 10-11: “이번 주 목적은 다른 팀원 기준으로 안드로이드 폰이랑 컴퓨터 정상적으로 연결된 상황에서 컴퓨터에서 readme.md에 따라 sh던 다른 절차던 terminal에 입력하는 것만으로도 컴퓨터에 백엔드 서버, 폰에 안드로이드 앱 띄워서 안드로이드 앱에 필요한 데이터가 백엔드 서버로부터 오도록 하는거임”
- 10-11: “아 그리고 fastapi에서 schema는 뭘로 선언하는중? sqlalchemy라면 그거 말고 fastapi답게 sqlmodel 사용해줘”
- 10-11: “나머지는 큰 문제 없어보이는데 fastapi project의 domain convention 반영해서 directory tree 구조 등 고려해서 개편 좀 해야겠다”
- 10-11: “안드로이드 앱 자체가 mock 기반으로 되어있었을텐데 코드 수정없이 백엔드 연결이 되었다고? ㅇㅅㅇ 설명을 좀 더 해줘야겠는데”
- 10-14: “아 사진크기제한은 하지마셈 내가 나중에 설득할게”
- 10-14: “그러면 앱에서는 2048에 메타데이터 남기는 쪽으로 해놓고, 서버는 그대로 보내는걸로”
- 10-14: “github wiki용 글도 기존 convention 엄격히 준수하여 작성했는지?”

## Codex inspection/documentation session — 2026-10-20

- “목적이 SWPP slide의 절차에 맞춰 /  현 수현, 혁준 최신 내용까지 반영하여 / 최종 iter2 통합본 PR 올리기 / SWPP가 요구하는 문서들에 내용 기록 이라면? DAG 재작업해줘”
- “별개로, /home/hyuk/PRJ/MyLittleChef/에서 stale 내용 rewrite 기반 최신화도 작업”

These inputs authorize local planning/documentation work; they are not evidence that the final integration PR or official Wiki publication has occurred.

## Integration execution — actual inputs, 2026-10-20

- “타 작업자의 변경사항 존중하여 가능한 원본 유지라는 policy 하에, handover DAG 전부 수행”
- “중간에 내 판단 필요하면 말하고, 아니면 계속 자율진행. 너가 언급한데로 test 강화 및 pre-commit까지만 도입하고, docker 등 SW는 iter3을 위하여 남겨놓음”
- “DAG 업데이트가 먼저인가?”
- “1. revision에 대해 프로젝트 내적인 단어 없이 나에게 설명. 누가 작업한 부분인지까지 2. 내가 준 자료 내에서 작업하면 될듯. pdf 중시”
- “revision 과정은 기존 gemini key로 안되나?”
- “뭘 하던 외부 공식문서 확인은 매우 권장”
- “무료  quota 소진까지는 나에게 문의 없이 자율 진행”

## Documentation and DAG correction — 2026-10-20

- “handover DAG 전부 수행”
- “프로젝트 문서 등 개선할거면 DAG에 PR 전에 추가해서 작업하는게 낫지 않나?”

This correction added document-source ownership and consistency verification before the final clone/report/PR gates. It did not authorize external Wiki/Sheet writes or remove the need for actual peer review.
