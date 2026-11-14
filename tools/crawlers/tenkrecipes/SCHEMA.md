# Offline parser output (stage 2)

The parser consumes an HTML string and its original URL. It never fetches a URL
or writes a file. `parse --input PATH --source-url URL` reads UTF-8 detail HTML
and emits the same detail record as JSON to stdout. Missing/unreadable inputs
and parse errors return nonzero. The source HTML remains unchanged.

An existing but blank DOM title raises `MissingTitleError`, a `ParseError`
subclass. Collection records it as `failed / missing_title` and preserves raw
HTML. A missing title element or required container remains a structural error.
JSON-LD does not replace an empty DOM title.

## List observations

`parse_list_page(html, source_url=...)` returns:

| Field | Type / meaning |
|---|---|
| `status` | `ok` or `empty` |
| `source_url` | Supplied list URL |
| `page` | Positive integer from URL, defaults to 1 |
| `category_code` | Source `cat4` string |
| `items` | Ordered observations, including repeated IDs |

Each item has `position` (one-based within page), `source_id` (string),
`source_url` (canonical recipe URL), `title`, and absolute `thumbnail_url`.
Candidate URLs must identify a numeric recipe on 10000recipe.com.
Requested cat2/cat4/order must match HTML form values, with cat2=18/order=reco.
An empty recognized container requires an explicit zero-result count. Missing
filters, containers, card links/titles/images, or invalid pages raise `ParseError`.
Deduplication, allocation, retrieval timestamps, and downloading are later stages.

## Detail records

`parse_recipe(html, source_url=...)` returns:

| Field | Type / meaning |
|---|---|
| `source` | `namespace` (`10000recipe`), string `id`, supplied `url`, optional `author`, `source_dates` |
| `title` | DOM title |
| `description` | DOM description, otherwise available JSON-LD description; null if absent |
| `servings_text`, `cooking_time_text`, `difficulty_text` | DOM text, or null; no conversion |
| `ingredients` | Ordered rows with `group`, one-based `order`, `name_raw`, `note_raw`, `quantity_text`, `source_material_id` |
| `steps` | Ordered rows with one-based `order`, `instruction`, `tips` (list), `image_urls` (absolute URL list) |
| `listed_tools` | List of `name_raw` and `evidence` (`source_url`, section label); null if unlisted, empty list if explicitly empty |
| `findings` | Diagnostic dictionaries described below |

Source dates retain available string values for `datePublished`, `dateModified`,
and `dateCreated`. JSON-LD author may be a name string or Person/Organization
object with a string name. The first Recipe object in source order is used,
including objects in arrays or `@graph`; unrelated and malformed scripts are
skipped. Multiple Recipe objects are not merged. DOM structure is still required.

DOM text uses readable text extraction with stripped text-node boundaries and
space separators; full markup is not reconstructed from JSON. Raw input HTML
is retained separately by the collection storage layer. Repeated ingredient
rows and steps remain separate. Missing quantities/notes/IDs remain null, and
source material IDs are never service ingredient IDs. Separate tips are not
concatenated into step instructions. Step image URLs are retained without fetching.
Only the explicitly labeled tool section is used, not actions, ads, or reviews.

Missing summary, DOM title, ingredient/step containers, ingredient name elements,
step body elements, or malformed labeled-tool structure raises `ParseError`.
Empty content lists are not a claim of successful acquisition; essential-content
and thumbnail validation belong to later collection stages. Present but empty
containers remain empty lists with missing-content findings. Blank name or
instruction elements remain null in their original rows with row-level findings;
rows are not dropped and JSON-LD does not fill these values.

## Findings

- `missing_quantity`: `field: ingredients`, one-based row `order`.
- `missing_ingredients`: `field: ingredients`; the ingredient list is empty.
- `missing_steps`: `field: steps`; the step list is empty.
- `missing_ingredient_name`: `field: ingredients`, one-based row `order`;
  the name element exists but its extracted name is null.
- `missing_instruction`: `field: steps`, one-based step `order`;
  the body element exists but its extracted instruction is null.
- `jsonld_unavailable`: no usable Recipe metadata was found. DOM extraction remains usable.
- `source_mismatch`: `field: title`, `status: review_pending`, `observations` with
  two entries containing `representation` (`dom`/`jsonld`), original extracted
  `value`, and `source_url`. DOM remains the output title.

Only nonempty titles available in both representations are compared, using HTML
entity decoding, Unicode NFC, trimming, and collapsing whitespace. Comparison
does not rewrite stored values. Ingredients, steps, and other metadata are not
compared. A finding is a mechanical diagnostic, not a semantic judgment or an
acquisition failure. No unit conversion, quantity completion, inferred tools,
semantic deduplication, production normalization, or service import occurs.

Validated thumbnails and image metadata are separate collection artifacts, not
changes to immutable detail parser records. See [RUNS.md](RUNS.md) for manifest
`images`, candidate outcomes, network-failure streaks, operator stops, resource
bounds, provenance, and resume behavior (run schema version 4).

`allocations` contains one `{source_id, category_code}` row per selected ID.
`failures` retains source/category/page/position/reason and available artifact
paths. `replacements` links failed and successful IDs within a category; it does
not imply semantic equivalence. `category_outcomes` records counts, deficits,
last page and the reason (`quota_reached`, `exhausted`, `repeated_page`, or a stop
cause). `collection_mode` is `pilot` or `quota` and controls subsequent CLI resume.
In quota mode, optional `quota_category` remembers a single-category execution
scope; absence means full traversal. Bare CLI resume preserves this scope,
and explicit `--full` removes it. It does not change the fixed plan or immutable
records, so existing schema-4 runs remain compatible. Single-category CLI/API
results expose `requested_category` and `category_complete`; canonical reports
still require the full 500-item target, independently of command exit success.
These mutable checkpoints never rewrite immutable source/parsed records.

## Offline acquisition reports

`reporting.validate_run(root)` checks the approved 500-ID plan, exact category
quotas, unique allocations and category observations, source identity, raw/JSON
hashes, essential content, and decoded original thumbnails. It performs no
network calls or writes. `reporting.write_report(root)` uses the same checks and
atomically publishes each of `report.json` and UTF-8-BOM `review.csv`.

The JSON separates `acquisition_complete`, `unique_success_count` (source IDs),
category targets/selected counts/deficits, `errors`, acquisition `failures`,
`replacements`, and source `findings`. Operator stops and retry deadlines remain
visible. Quality findings have `review_pending` status; unlisted tools are
reported as `tools_not_listed`. Title mismatches retain both original
observations and their URLs, including in the CSV's JSON `observations` cell.
CSV rows link raw HTML, parsed JSON, and original thumbnail paths where present.

`count_basis: source_id`, `semantic_uniqueness_guaranteed: false`, and
`semantic_duplicate_review: {status: pending, required_before_production: true}`
explicitly distinguish acquisition from mandatory later semantic review. No
production-ready decision, quantity completion, or semantic merging is made.
Repeated reports against unchanged inputs are deterministic. Each output is
atomic independently; the pair is not a multi-file transaction, so regenerate
both after an interrupted publication.
