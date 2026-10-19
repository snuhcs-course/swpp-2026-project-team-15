# PM handoff and project operating guide

[English](pm-handoff.md) · [한국어](pm-handoff.ko.md)

Updated 2026-10-20, Iteration 2. The prior schedule names Hyeokjun as Iteration 1 PM and Ahyoon as Iteration 2 PM; verify any later rotation against the current schedule. This guide records existing process and current boundaries, without assigning new obligations or deadlines to teammates.

## Current handoff

PR #6 is merged into main `a27bf0a`. Android, database and historical research artifacts are now included; the local baseline reaches recipe detail through FastAPI. This feature branch preserves and integrates Hyeokjun88d3380 (including backend1edadc0, PRs #9/#10) and Suhyeon89fc8ba. Main merge and peer review remain pending. See the [root README](../README.md) for exact heads, setup and limits.

Catalog versioning, name-to-ID mapping, DTO/status handling, ordering, request guards and favorite-original restoration are implemented and tested. See [integration evidence](iterations/iteration-2/README.md) and [publication sources](submission/iteration-2/README.md). Allergy/tool matching, authoritative one-serving amounts and semantic AI quality remain incomplete.

## Sources and evidence

| Item | Source |
| --- | --- |
| Tasks, actual workers, hours/tokens, final commits | Team schedule; agents have READ-ONLY access and prepare local PM drafts |
| Code/review/merge | GitHub branches and PRs |
| Meeting times and key decisions | [Meeting log](meetings/README.md) |
| Durable technical choices | [Decision log](decisions.md) and Wiki |
| Current execution and limitations | [Root README](../README.md) |
| Prior boundary record | [Iteration 1 status](iterations/iteration-1-status.md), preserved as historical |

Code and Wiki are separate Git repositories. Code changes do not publish Wiki drafts automatically. Official Wiki was still October 9 revision when checked October 20.

## Iteration procedure

1. Confirm the current goal and existing schedule ownership. Preserve P identifiers and let the PM assign added A identifiers. Record only real workers/participants and measured effort.
2. Prepare requirements/API and testing plans, implement with unit/regression tests, push a focused branch, open a PR, review/merge, then verify critical flows on merged main. Preserve shared history and attribution.
3. Record actual meeting time/key points and decisions, not invented meetings or private message dumps. Use the [meeting template](meetings/TEMPLATE.md).
4. Align Requirements, Design, Testing and AI Report with the actual code and evidence. Testing needs Plan and Results, date/SHA/commands/counts/coverage/targets/exclusions/screenshots. AI report uses current v1.1, not blanket code-marker requirements. Formal≥30 frozen AI cases are due Iteration 3.
5. Publish and read back actual Wiki revisions. Prepare `iteration-2-demo`, root setup/features/limitations, a short demo video, required Wiki PDFs and schedule XLSX. Check eTL upload/deadline evidence separately; none is completed merely by drafting.
6. Hand over open PRs, unresolved policies, known gaps, evidence locations and access status. Do not send credentials through Git.

Private data, generated SQLite files, keys and raw chats stay outside Git. Confirm data redistribution rights and authorization for new dependencies/paid calls. Preserve existing UI/design when connecting data.
