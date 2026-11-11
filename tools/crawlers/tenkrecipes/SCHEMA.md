# Offline parser output (stage 2)

The parser consumes an HTML string and its original URL. It never fetches a URL
or writes a file. `parse --input PATH --source-url URL` reads UTF-8 detail HTML
and emits the same detail record as JSON to stdout. Missing/unreadable inputs
and parse errors return nonzero. The source HTML remains unchanged.

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
must be retained separately by the future storage layer. Repeated ingredient
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
