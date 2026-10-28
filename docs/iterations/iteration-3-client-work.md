# Iteration 3 client work

Owner: Hyeokjun Kwon. Target completion: 2026-11-04.
Base: e621ffd6ba52fca23d0fc4f0ab15530a6b99406a (main, checked 2026-10-28).
Local branch: frontend/iter3-inventory-and-images.

## Agreed behavior

- Long-press an ingredient or enter 관리 mode to request deletion. Both use the same named confirmation. Cancel changes nothing. Persist only the selected name; failed writes must not appear successful.
- Entering recipes uses the latest inventory. Older responses must not overwrite newer results.
- Cards show a missing count and at most two names; details distinguish missing items with text and color. Respect server staple assumptions and avoid stale availability claims.
- Map the agreed 20 ingredients plus approximately 10 high-frequency additions. Related forms may share artwork without sharing inventory identity. Select 20 matching recipe photos keyed by recipe ID, with fallbacks.
- Use public artwork with source/author/license/edit records and in-app credits. Bundle assets in the APK.
- Keep existing API/deployment configuration and protected contributor tests/references.
- Cooking-completion cleanup is a deferred idea pending team discussion.

## Target dates (not actual completion dates)

| Target | Checkpoint |
| --- | --- |
| October 28 | Baseline, branch, plan and AI record setup |
| October 29 | Deletion, persistence and recommendation freshness |
| October 30 | Priority ingredient icons |
| October 31 | Missing-ingredient display |
| November 1 | Recipe photos and credits |
| November 2 | Required flow integration |
| November 3 | Device checks and blocking fixes |
| November 4 | Final checks, report evidence and one PR |

## Review checkpoints

Explain each change in Korean: files, key functions, data flow and a small excerpt Hyeokjun can read. Record his predictions, app observations and direct edits only after they happen. Do not invent mistakes or manual fixes for the report.

Use the isolated cloudTest package. Automated checks use controlled local APIs. Keep feature commits local until Hyeokjun reviews the result and authorizes publication.

## Actual state

- Baseline and first deletion checkpoint: implemented and automatically verified on 2026-10-28; human review pending.
- Icons, missing display, recipe photos, final user review and PR: not started.
- Human code review / manual edits for this checkpoint: not yet performed.
- Broad recommendation/recognition recovery UX remains optional; fix blockers in the required flow.

Actual evidence: [AI work log](../ai-collaboration/iteration-3/hyeokjun-work-log.md).
Original inputs: [prompt log](../ai-collaboration/iteration-3/hyeokjun-prompts-2026-10-28.md).
