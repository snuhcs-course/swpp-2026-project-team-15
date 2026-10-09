# PM handoff and project operating guide

[English](pm-handoff.md) · [한국어](pm-handoff.ko.md)

Current iteration boundary: Iteration 1 ends 2026-10-09. The completed schedule names **Hyeokjun Kweon** as Iteration 1 PM and **Ahyoon Choi** as Iteration 2 PM. Later PM rotation is recorded in the team schedule; check the latest workbook rather than copying this list into future reports.

## Sources of truth

| Item | Location | Maintain when |
| --- | --- | --- |
| Tasks, owners, planned/actual hours, final commit | Team schedule workbook (`team15-iter1-schedule.xlsx` for Iteration 1 submission) | Work is added or completed; before submission |
| Code and review | Git branches and pull requests | Each implementation change |
| Meeting outcomes | [`docs/meetings/`](meetings/README.md) | After each team or TA meeting |
| Product/technical choices | [`docs/decisions.md`](decisions.md) | A choice is made or revised |
| Technical explanation | [GitHub Wiki](https://github.com/snuhcs-course/swpp-2026-project-team-15/wiki) | Design, research, or data behavior changes |
| Current implementation state | [`docs/iterations/`](iterations/iteration-1-status.md) | At each iteration boundary |

The code repository and Wiki are separate Git repositories. A pull request to the code repository does not update the Wiki automatically.

## Each iteration

1. **Start:** read the prior status and meeting log; confirm the PM, owners, iteration goal, acceptance evidence, and deferred work in the schedule. Do not assume a proposed feature is implemented.
2. **Plan:** keep existing `P` identifiers. Add new tasks as `A1`, `A2`, etc. in date order; record actual participants and workers, not the whole team by default. Split work small enough to show distinct deliverables.
3. **Work:** use focused branches and pull requests. Link tasks to commits/PRs and keep setup instructions with the code. Review other branches before describing the project as integrated.
4. **Meet:** use the [meeting template](meetings/TEMPLATE.md). Record decisions, options, actions, owners, and due dates. Move durable choices into the decision log and relevant Wiki page.
5. **Close:** reconcile task status and human/agent hours with actual work; record the relevant final commit ID for each completed task. Check links, data counts, demo behavior, and claims against the current branch. Mark deferred work explicitly for the next iteration.
6. **Submit:** export the course documents from reviewed sources and use the exact course naming convention. For Iteration 1, the ZIP is `team15-iter1.zip` with `team15-iter1-reqspec.pdf`, `team15-iter1-design.pdf`, `team15-iter1-schedule.xlsx`, and `team15-iter1-AI-collaboration-report.pdf`. Verify the course portal deadline and uploaded archive separately.

## Branch and data conventions

- `main` is the integration branch. The Iteration 1 Android, recipe DB, and research deliverables are still on separate branches; see [status](iterations/iteration-1-status.md).
- Prefer `feat/<topic>` for team feature work; documentation maintenance may use a focused `docs/<topic>` or `codex/<topic>` branch. Open a PR with scope, evidence, limitations, and review owner before merging.
- Do not commit raw private chat, passwords, API keys, local database files, or the separately distributed CSV bundle. Summarize meeting decisions instead. The repository's `.gitignore` excludes local data and generated output.
- Before using the course-provided OpenAI API key, agree on budget/usage limits and store it outside Git. GPU/CPU server access is an optional resource until provisioned and tested.

## Iteration 2 handoff

- Coordinate replacement of Android mock responses with the two server flows and agree on request/response examples.
- Select a pilot recipe set and ingredient vocabulary for one-person cooking. Finish quantity, tool, and allergen information needed by recommendation filters.
- Evaluate photo recognition with real images and record failure cases; retain manual correction and consider a seasoning checklist.
- Define recipe refresh, missing-ingredient suggestions, and restricted AI substitutions before promising them as features.
- Decide inventory persistence, backend framework, and ORM based on the API and data needs, then update the decision log/Wiki.
- Keep the TA meeting action list and schedule aligned; carry unfinished Iteration 1 work forward with a new planned task rather than silently marking it done.

## Handoff note for the outgoing PM

Before the next PM takes over, provide the current schedule, open PRs/branches, outstanding TA feedback, Wiki pages, demo instructions, and a short list of decisions waiting for the team. Confirm that each person can access the repository and relevant course resources. Avoid sending credentials through the repository.
