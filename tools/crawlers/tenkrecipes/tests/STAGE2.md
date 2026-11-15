> Historical implementation-stage record. Counts, filenames and contract notes
> below describe past executions. See [README.md](README.md) for current tests,
> policy boundaries and the old-to-current filename map.

# Stage 2 test-first contracts

These tests cover the implemented tasks 2.1–2.4 and the offline parse CLI.
They were first written RED, then implemented without skip/xfail or replacement
parsers in the harness. Stage 1 and existing Pixabay contracts remain required.
See [the runtime schema](../SCHEMA.md) for the current output and error contract.

## Fixture provenance and limits

`fixtures/stage2_list.html` and `fixtures/stage2_detail.html` are hand-authored
synthetic HTML. They use structures observed during the earlier exploration
(`common_sp_list_li`, the confirmed-material container, step and tip classes).
All recipe content, IDs, authors, image paths, and source dates are test data.
No page or image was downloaded to create these fixtures, and the tests do not
request their URLs. These tests verify the agreed extraction behavior on those
structures; they do not establish compatibility with every live page layout.

Variants remove or alter explicit fixture fragments, or replace only JSON-LD.
They do not run a replacement parser or compute expected content through the
production parser. Expected ingredient and instruction values are stated
independently in the assertions.

## Public interface

The test-first interface is now implemented:

```python
from crawlers.tenkrecipes.parsing import ParseError, parse_list_page, parse_recipe

page = parse_list_page(html, source_url=list_url)
record = parse_recipe(html, source_url=recipe_url)
```

Both functions are offline and consume an HTML string. `ParseError` is the
controlled exception for unrecognized structure or list/filter mismatches.
The tests import the parser during individual test execution, preserving the
original test-first discovery behavior.

### List output

- `status`: `ok` or `empty`. An empty recognized list with an explicit zero
  result count differs from an unrelated page, missing filters, or changed layout.
- `source_url`, `page`, `category_code` (source cat4 string).
- `items`: source-order observations with one-based page-local `position`,
  string `source_id`, absolute `source_url`, `title`, and absolute `thumbnail_url`.
- The URL's requested cat2/cat4/order must agree with the form values. Relative
  links are resolved from the source URL. Recipe images must be distinguished
  from video badges and avatars; unrelated links outside cards are ignored.
- Repeated IDs are preserved as observations, not selected twice as records.
  Allocation and record deduplication belong to later stages. Different IDs with
  the same title are also retained.

### Detail output

- `source`: `namespace: "10000recipe"`, string `id`, `url`, available `author`,
  and `source_dates` keyed by the original JSON-LD names such as `datePublished`.
- `title`, `description`, `servings_text`, `cooking_time_text`, `difficulty_text`.
  DOM summary text stays in its original units/language. Missing optional values
  are `None`; no quantity, serving, duration, or difficulty is invented.
- `ingredients`: ordered row dictionaries with `group`, `order`, `name_raw`,
  `note_raw`, `quantity_text`, and `source_material_id`. Group labels retain their
  brackets. Order is one-based across groups. A source material ID is not a
  service ingredient ID, and no service classification is inferred.
- `steps`: one-based `order`, `instruction`, `tips` (list of text), and
  `image_urls`. Separate tip elements do not get concatenated into instructions.
  Repeated ingredient IDs and repeated instructions remain separate rows/steps.
- `listed_tools`: source-order tool dictionaries with `name_raw` and nonempty
  source `evidence`. `None` means no section was listed; `[]` means a listed
  section is empty. Neither implies a complete inventory of required tools.
  Tools are not inferred from actions or user reviews and are not ingredients.
- `findings`: dictionaries with `code`, including `missing_quantity`,
  `jsonld_unavailable`, and `source_mismatch` for the tested conditions.
  Additional diagnostic fields are allowed.

JSON-LD object, array, graph, and multiple-script forms are tested with unrelated
metadata before Recipe. If JSON-LD is absent or malformed but the DOM is intact,
use the DOM and report unavailable metadata. DOM is the extraction baseline for
title, description, summary, ingredients, steps, tips, and listed tools. JSON-LD
supplements unavailable metadata such as description, author, and source dates;
it does not overwrite present DOM values or fill missing ingredient quantities.
Serving/time text is not synthesized from JSON-LD durations or translated yields.

Stage 2 compares only titles when both representations provide a nonempty title.
Comparison decodes HTML entities,
applies Unicode NFC, trims ends, and collapses whitespace runs to one space.
Different normalized titles produce a `source_mismatch`. Ingredients, steps,
and other metadata are not compared. Missing titles do not constitute mismatches.
No unit conversion,
synonym matching, fuzzy alignment, semantic judgment, or automatic correction is
performed. Comparison normalization never overwrites preserved source values.

When normalized values differ, output still uses DOM and retains both original
values in a `source_mismatch` finding. This is a mechanical difference diagnostic,
not proof that the recipe is wrong or an acquisition failure. The finding is:

- `field`: `title`.
- `status`: `review_pending`; optional later content review remains pending.
- `observations`: one entry per representation, each with `representation`
  (`dom` or `jsonld`), `value`, and `source_url`.
  Title values retain each representation's extracted text.

The conflict test checks DOM precedence along with both values and origins.
DOM precedence is an extraction policy, not a guarantee of source accuracy.
The source URL is
sufficient provenance for a conflict finding; no DOM selector, JSON path, or
additional saved-file/hash reference is required in that finding.
Automatic semantic ingredient/step consistency judgment and duplicate
adjudication are outside stage 2.

### Offline CLI

From `tools/`, invoke:

```powershell
python -m crawlers.tenkrecipes.cli parse --input source.html --source-url https://www.10000recipe.com/recipe/900001
```

It emits the detail record as JSON to stdout. It does not alter the input or
create files in its working directory, and does not download referenced images.
A missing input is an input-file error; an empty or unrelated document is a
parse error. Either must return nonzero and preserve any existing source file.
The existing subprocess audit guard checks network and production-file isolation.

## Coverage and execution

| Task | Cases | Main checks |
|---|---:|---|
| 2.1 | 14 | Combined filters, candidate observations, links/images, empty versus changed structure |
| 2.2–2.3 | 29 | DOM precedence, metadata supplementation, mechanical title comparison including Unicode, rows/quantities/notes, steps/tips, missing-content findings, tools and source identity |
| 2.4 | 4 | Offline parse command, missing/invalid input, source hash and no output-file side effects |

```powershell
uv run --locked pytest crawlers/tenkrecipes/tests/test_stage2_lists.py crawlers/tenkrecipes/tests/test_stage2_details.py crawlers/tenkrecipes/tests/test_stage2_parse_cli.py -q
```

The implementation adds four boundary cases for canonical Unicode title equality,
a malformed script before valid metadata, JSON-LD quantity not filling a blank
DOM quantity, and metadata not concealing missing DOM structure.
These fixtures do not establish compatibility with every live page layout.

Four regression cases reproduce a violation of the requirement that missing
values have quality findings: empty ingredient/step containers and blank
ingredient names/instructions. They failed before the diagnostic fix. Empty lists
and null row values remain preserved, while absent structural elements continue
to raise `ParseError`. Acquisition eligibility is still checked in later stages.
