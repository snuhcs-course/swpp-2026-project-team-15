# Decision log

[English](decisions.md) · [한국어](decisions.ko.md)

Use this page for choices that affect scope, architecture, data, or the user experience. Record the meeting date, the evidence, and whether a choice is agreed or still under evaluation. Update the relevant Wiki page when a technical decision is settled.

| Date | Topic | Current position | State / next check |
| --- | --- | --- | --- |
| 2026-09-14 to 2026-09-16 | Product direction | Support small-household cooking from ingredients already at home. | Agreed project direction; first proposal followed. |
| 2026-09-23 to 2026-09-25 | User flow | Photo-assisted ingredient entry with user review and an editable fridge inventory, followed by recipe browsing/detail. | Wireframes and prototype; usability and accuracy remain to be checked. |
| 2026-10-04 to 2026-10-06 | Recipe storage | Start with a local SQLite schema and entity CSV import to inspect the data; consider ORM and serving APIs during integration. | Prototype choice; production DB/ORM not yet selected. |
| 2026-10-07 | Server responsibilities | Separate image analysis into candidate ingredients from recommendation using confirmed inventory and user constraints. | Agreed direction; API contracts and deployment pending. |
| 2026-10-07 | Target audience | Make the recipe set and quantities suitable for one person and available cooking tools. | Iteration 2 data curation needed. |
| 2026-10-07 | Recommendation behavior | Show feasible recipes first; consider refresh, missing-ingredient suggestions, and limited AI substitutions with clear boundaries. | Product behavior discussed; ranking and safety rules still need specification. |
| 2026-10-07 | Ingredient entry | Balance low effort against recognition errors. Consider a separate checkbox/onboarding path for pantry seasonings that photos may miss. | Compare options with real photos and users. |

## Open choices

- Backend framework and API contracts; FastAPI and Django have been considered, but no final implementation choice is recorded.
- Inventory source of truth and synchronization between device and server.
- Recognition model/provider, test image set, and acceptable correction burden.
- Recipe/tool/allergen mapping and one-person quantity conversion rules.
- Exact scope, validation, cost controls, and disclosure of AI recipe adjustments.

When a choice is resolved, replace the open item with a dated entry above and link its implementation or experiment.
