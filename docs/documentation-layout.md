# Documentation ownership and publication

The code repository and the GitHub Wiki are separate repositories. No workflow
automatically synchronizes them in either direction. CI checks local source
consistency; it does not publish or confirm a Wiki revision.

| Location | Role | Editing rule |
| --- | --- | --- |
| Root README | Current setup, features and known limits | Link detailed evidence rather than duplicating every result |
| docs/iterations/iteration-2 | Input manifest, contract, execution and report evidence | Record the actual code/data/run; distinguish historical and fresh results |
| docs/submission/iteration-2/wiki | Single editable source for current Iteration 2 Wiki pages and figures | Edit here, review the manifest diff and publish separately through the user |
| docs/submission/iteration-1 | Dated submission sources | Preserve historical wording; do not rewrite as current implementation |
| docs/ai-collaboration/iteration-1 | Contributor inputs and team draft history | Evidence for that iteration, not an additional current Wiki source |
| docs/meetings and decisions | Real discussion and durable decisions | Preserve attribution and history; agent sessions are not team meetings |
| docs/acceptance | Protected human specification references | Agents must not edit; integrity checks complement human review |
| docs/demo | Synthetic deterministic test input | No private photos or dataset redistribution |

Korean pages may be explanatory guides rather than complete translations; the
English course documents are the publication sources. Each Korean page states its
role. Private workspace notes, original PDFs/datasets, raw model responses and
generated PDF/HTML previews are outside the team repository. The local
`vault/drafts/wiki` directory now contains navigation pointers instead of editable
copies. Generated previews must not be edited as source documents.

## Local publication checks

From the repository root:

```sh
python3 scripts/check_publication.py
# After intentional source changes, update hashes and review the diff:
python3 scripts/check_publication.py --update-manifest
git diff -- docs/submission/iteration-2/publication-manifest.json
```

The check validates local page/image links, hashes, preserved functional/NFR
wording and the AI contribution draft's six sections/word range. It does not
validate product completeness, semantic AI quality, all teammates' interaction
records or the contents of an external Wiki. Preserved Wiki page names refer to
the recorded official baseline; they are not newly created local duplicates.

Publication is a separate user action: review the source diff against the current
Wiki, apply the selected pages/images without overwriting unrelated history, then
provide the actual Wiki revision for read-only confirmation. Record that revision
and source/export hashes before treating PDFs as official exports. A feature PR,
local manifest or preview never establishes publication or eTL submission.

## Reproducible previews

With pandoc, Chrome and pdfinfo installed, run `python3 scripts/export_publication.py` from the repository root (or supply `--output-dir`). The default output/ directory is ignored by Git. The exporter reads the canonical sources, records source/PDF hashes and page counts in export-provenance.json, and checks the AI preview fits one page. It does not create editable Wiki copies or publish externally. Font/browser versions can affect pagination; a failure must be resolved before treating the preview as ready.
