# Iteration2 integration evidence

Updated2026-10-20. This directory records the integrated branch, distinct from historical baseline results. Official Wiki publication and submission are separate user actions.

- [Implementation contract and test plan](integration-contract.md)
- [Input/database manifest](input-manifest.json)
- [Quality environment and protection limits](quality-environment.md)
- [Original contributor-test hashes](test-baseline.json)

Current local checks: server179 passed, expanded app/filtering/revision coverage98%; Android JVM34 passed in a forced fresh run; S22 Android14 connected tests10 passed, including real local HTTP catalog/recommendation and rendered detail. No actual paid provider call is included in those results. Exact final SHA, commands, coverage details and CI links are recorded in the execution report when finalized. One new UI assertion initially used exact membership instead of its intended status text; it was corrected to the full expected string and the complete suite rerun, without skipping/deleting original tests.
