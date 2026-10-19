# AI Collaboration Report – Iteration 2

**Local publication source, updated 2026-10-20.** Jaehyuk Choi's contribution; team consolidation and official publication remain pending. Tools: Claude Code (Opus 5.5, historical contributor record), Codex (current integration), gemini-3.5-flash-lite (recorded live checks). Exact Codex model/time savings are not invented.

## 1. Where AI was used

Claude Code assisted the original FastAPI/SQLModel recognition backend, Android wiring/photo preparation, tests, CI and demo script in PR #6. Codex reviewed the latest client and recommendation work, prepared the local course wiki/DAG, and integrated canonical mapping, new response handling, request states, favorite-original restoration, flow tests and pre-commit. Hyeokjun's DataStore/sorting and Suhyeon's filtering/revision implementations and original commits were preserved. Changes to original files were limited to necessary integration boundaries; new adapters carried most additional behavior.

## 2. Prompt history

Selected user inputs are preserved verbatim:

- “타 작업자의 변경사항 존중하여 가능한 원본 유지라는 policy 하에, handover DAG 전부 수행”
- “무료  quota 소진까지는 나에게 문의 없이 자율 진행”

The separate Prompt Log preserves more original inputs. Available interaction records and contributor notes were reviewed; other members’ full Iteration 2 sessions were not provided, so this remains a contribution draft for team consolidation. Private session history and credentials are not published wholesale.

## 3. What AI did well

The audit identified incompatible ingredient IDs, an old name-based client endpoint, partial AI failures inside HTTP200, request-duration mismatch and incomplete favorite restoration. Integration retained the original algorithms while exposing a catalog fingerprint and restoring original recipes without extra AI calls. Existing tests were collected more completely, including experiment tests and previously unmeasured filtering/revision packages. New checks exercised state transitions, file reopening, cancellation, sorting and real device networking rather than relying only on signatures. Official technical documentation helped confirm DataStore lifecycle, cancellation, test semantics and Gemini compatibility.

## 4. Hallucinations and errors

Earlier report drafts overstated simulated research results, generalized image-token observations into constant cost, and retained a superseded AI-code marker rule. Those claims were rewritten with scope and history preserved. During this integration, pre-commit initially classified imports differently because it ran from another directory; matching CI's working directory fixed it without editing contributor tests. A new UI assertion expected a partial status string under exact-match semantics; it was corrected to the full expected text and rerun. The first live helper accepted exact names only, so it omitted the documented egg alias; a second preserved run aligned it with the client contract.

## 5. Prompt revisions

The user first requested broad DAG execution, then clarified preservation of other contributors' work, test strengthening/pre-commit, deferral of deployment software, PDF priority and official-document consultation. These refinements narrowed integration toward additive adapters and observable scenarios. The question about reusing the existing Gemini key corrected an unnecessary request for separate credentials. Explicit free-quota authorization allowed bounded real checks while leaving ordinary development and CI on mock providers. A later user correction added document ownership, duplicate-source cleanup and consistency checks as explicit pre-PR DAG gates. External Wiki/Sheet/portal changes remained read-only and were prepared as user-action drafts.

## 6. Manual fixes and why

The user supplied product/scope decisions and challenged assumptions; this report does not invent manual code edits or independent human review. Codex performed the current code changes and checks. Local server tests reached 181 passed with 98% expanded combined coverage; Android JVM 34 passed and S22 connected 10 passed. Live recognition and adjustment requests returned structured outcomes, including explicit refusals when essential ingredients were absent. A fresh clone exposed missing importer path arguments hidden by an existing DB; an explicit-path fix and shell regression followed. These results do not establish safe cooking, complete allergy/tool filtering or a finished formal AI evaluation. Actual PR/CI, peer review, official publication and merged-main results must be recorded separately as they occur.
