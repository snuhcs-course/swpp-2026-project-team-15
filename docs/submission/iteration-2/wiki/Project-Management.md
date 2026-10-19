# Project management and handoff

The team records schedule details in the course workbook and keeps meeting outcomes, decisions, and PM handoff steps next to the code. This Wiki page is an index so future PMs can find the operational record without copying it into two places.

## Iteration 1 state — retained historical record

Iteration 1 closes on 2026-10-09. Hyeokjun Kweon is the Iteration 1 PM; the schedule names Ahyoon Choi as the Iteration 2 PM. The Android UI, recipe DB, and research work live on separate branches. The end-to-end app/server flow is still integration work.

## Operational documents

- [Iteration 1 status and evidence](https://github.com/snuhcs-course/swpp-2026-project-team-15/blob/main/docs/iterations/iteration-1-status.md)
- [Dated meeting log](https://github.com/snuhcs-course/swpp-2026-project-team-15/blob/main/docs/meetings/README.md)
- [Decision log and open choices](https://github.com/snuhcs-course/swpp-2026-project-team-15/blob/main/docs/decisions.md)
- [PM handoff checklist](https://github.com/snuhcs-course/swpp-2026-project-team-15/blob/main/docs/pm-handoff.md)

## Submission documentation

- [[Requirements-and-Specifications]] and [[Requirements-and-Specifications-ko]]
- [[Design-Documentation]] and [[Design-Documentation-ko]]

The English Wiki pages are the course-facing versions. Their Markdown sources and Korean counterparts are in the [documentation PR](https://github.com/snuhcs-course/swpp-2026-project-team-15/pull/2) under `docs/submission/iteration-1/`. The Word/PDF copies should be checked against these pages before submission. Annotated screen wireframes still need to be added to the Requirements & Specifications PDF and Wiki page.

For technical detail, see [[Design-Documentation]], [[Pipeline-Candidate-Comparative-Evaluation]], and [[Recipe-Database]]. The research benchmark is a limited simulation and should not be cited as measured real-photo recognition quality.

## Iteration 2 integration — 2026-10-20 local publication source

The feature branch integrates Hyeokjun88d3380 (backend1edadc0) and Suhyeon89fc8ba on main a27bf0a, preserving their histories and contributor tests. It adds ID mapping, explicit AI outcomes, request/error states, favorite original restoration and scenario checks. This is a local publication source; it has not changed the official Wiki.

- [Integration process and actual contributions](https://github.com/snuhcs-course/swpp-2026-project-team-15/blob/feat/iter2-final-integration/docs/iterations/iteration-2/process-record.md)
- [Execution evidence](https://github.com/snuhcs-course/swpp-2026-project-team-15/blob/feat/iter2-final-integration/docs/iterations/iteration-2/execution-report.md)
- [[Testing-Documentation]] and [[AI-Collaboration-Report-Iteration-2]]

The user/agent working record is not a team meeting or TA review. Original P-task assignments are retained; unknown effort/token totals and review outcomes remain unfilled. The schedule is read-only for agents. Official Wiki publication, peer review/main merge, TA feedback and eTL submission need actual evidence.
