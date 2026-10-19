# My Little Chef — Requirements and Specifications

**Team 15 · Iteration 2 · 2026-10-20 · version 0.4**

**Languages:** [[English|Requirements-and-Specifications]] · [[한국어|Requirements-and-Specifications-ko]]
**Scope:** The requirements below describe the intended product. Current Iteration2 implementation and remaining gaps are stated separately; original stories/AC remain unchanged.

**LOCAL PUBLICATION SOURCE — not yet posted.** Original US/AC wording remains unchanged; the status table below identifies incomplete requirements. Technical baseline: integration commits3de29f6/9454e4c on main a27bf0a, including Hyeokjun88d3380 and Suhyeon89fc8ba.

## Document Revision History

| Version | Date | Changes |
| --- | --- | --- |
| 0.1 | 2026-09-30 | Initial requirements based on the proposal and early research: target users, ingredient registration, and recipe recommendations. |
| 0.2 | 2026-10-07 | Updated the scope using the Iteration 1 prototype, recipe data, and TA feedback on one-person meals and practical constraints. |
| 0.3 | 2026-10-09 | Refined six mandatory user stories, candidate features, and the UI flow. |
| 0.4 | 2026-10-20 | Integrated behavior and requirement/verification gaps; preserved original stories/AC |

## Project Abstract

My Little Chef helps Korean students and other people living alone choose meals using ingredients they have confirmed. Users photograph food, review and correct candidate names, and save the chosen items in a digital refrigerator. The current increment persists that inventory and the user profile, maps ingredient names to the server catalog, and presents filtered recipes with quantities, steps and missing ingredients. Users can sort results, save favorites and restore original recipe details after reopening the application. Any AI suggestion is clearly separated from the original, including explicit refusal or failure outcomes. The completed product is intended to support small kitchens, cooking tools, allergy restrictions and practical serving information. Those intentions are not all delivered: reliable tool/allergen metadata, authoritative one-serving conversion and original-source URLs remain gaps. Users must not interpret a successful AI response as verified cooking safety. This iteration concentrates on a reproducible client–server flow, transparent state handling and evidence-based integration testing rather than claiming complete recipe suitability.

## Customers and Use Context

The general audience is anyone who wants meal ideas from food already at home. The primary users are Korean university students and other single-person households with small refrigerators, limited cooking tools, limited portions, and little cooking experience. A secondary user is someone who has an allergy restriction and needs the application to avoid unsupported safety claims.

Two common occasions are: (1) deciding what to cook after opening the refrigerator, and (2) registering a few newly purchased ingredients without re-entering the entire inventory. The product should not require a perfect photograph or a complete inventory before the user can continue.

## Competitive Landscape — retained October9 comparison

Samsung Food+ already describes photo-based ingredient scanning, a food list, recipe search using available ingredients, and AI recipe personalization. The Korean app Naenggo advertises photo or text ingredient input and AI recipe recommendations. My Little Chef therefore does **not** claim those individual features are new. Its intended focus is the combined decision: *Can a beginner living alone make this one-serving Korean meal now, with their confirmed ingredients, available cooking tools, and allergy restrictions?* The application should show the missing conditions and keep any adjustment separate from the source recipe. This is a proposed product direction, not a claim that these functions have already been implemented or that competitors cannot provide them.

| User need | Samsung Food+ | Naenggo | My Little Chef requirement |
| --- | --- | --- | --- |
| Register ingredients from a photo | Documented | Advertised | Reviewable candidates plus manual correction |
| Discover recipes from available food | Documented | Advertised | Rank meals by confirmed ingredients and missing essentials |
| Account for limited cooking tools | Not assessed here | Not assessed here | Filter or clearly flag unavailable tools |
| Show a practical one-serving source recipe | Not assessed here | Not assessed here | Provide one-serving quantities with source attribution |
| Explain a constrained recipe adjustment | AI personalization documented; behavior differs by product | Not assessed here | Label changes and apply explicit safety restrictions |

Sources: [Samsung Food+](https://samsungfood.com/food-plus/), [Samsung Food Help: ingredient-based search](https://support.samsungfood.com/hc/en-us/articles/30251599415956-How-to-Search-for-Recipes-Using-Your-Available-Ingredients), [Naenggo on Google Play](https://play.google.com/store/apps/details?id=com.naengo.app).

## Functional Requirements

US-01 to US-06 are the team's proposed mandatory stories for the completed product. The Iteration 1 prototype does not yet satisfy every criterion. The course requires every mandatory story to be implemented by the end of the project, so the team should narrow any story it cannot commit to delivering.

### US-01 — Set cooking constraints

**As a** beginner cook, **I want** to save my cooking tools and allergy restrictions, **so that** recipe results reflect what I can safely make in my kitchen.

- **Given** a first-time user, **when** they finish onboarding with selected tools and allergies, **then** the application saves those selections and shows them when the profile is reopened.
- **Given** a user changes a restriction, **when** they request recommendations again, **then** the new selection is used for those recommendations.

### US-02 — Review recognized ingredients

**As a** user with food in my refrigerator, **I want** to photograph several items and correct recognition results before saving them, **so that** incorrect detections do not silently affect my inventory.

- **Given** a photograph has been analyzed, **when** candidate ingredients are returned, **then** the user can confirm, remove, or manually add items before saving.
- **Given** recognition fails or returns no useful candidates, **when** the result screen appears, **then** the user can retry or enter an ingredient manually.

### US-03 — Maintain an available-ingredient list

**As a** user, **I want** to see and edit the ingredients I currently have, **so that** later recommendations use the corrected list.

- **Given** confirmed ingredients, **when** the user saves them, **then** they appear in the digital refrigerator without unintended duplicate entries.
- **Given** an ingredient is no longer available, **when** the user removes it, **then** subsequent recommendations no longer treat it as owned.

The refined proposal uses **availability** for the MVP. Tracking exact remaining amounts is an open requirement after the TA discussion; the team must decide how users would enter and update quantities before adding quantity-specific acceptance criteria.

### US-04 — Find feasible recipes

**As a** person living alone, **I want** recipe results to account for my ingredients, allergies, and cooking tools, **so that** the app does not present an unsuitable dish as immediately cookable.

- **Given** confirmed ingredients and user constraints, **when** the user opens recommendations, **then** each result indicates whether it can be prepared now or which ingredients or tools are missing.
- **Given** a known allergy conflict, **when** recommendations are produced, **then** the conflicting recipe is excluded from the safe candidate set.
- **Given** no feasible recipe, **when** results are shown, **then** the app explains why and offers a way to revise the input or view recipes requiring additional ingredients.

### US-05 — Inspect a source-grounded one-serving recipe

**As a** beginner cook, **I want** to inspect a one-serving recipe with its source, amounts, steps, and missing items, **so that** I can decide whether to cook it.

- **Given** a recipe result, **when** the user opens its details, **then** the original recipe source, ingredient list, instructions, serving information, and missing conditions are visible.
- **Given** source amounts are not yet converted reliably to one serving, **when** the detail is displayed, **then** the app does not present an unverified conversion as authoritative.

### US-06 — Save and refresh recipe choices

**As a** user, **I want** to save recipes and request another relevant result, **so that** I can continue looking when the first suggestion does not appeal to me.

- **Given** a recipe card, **when** the user saves or unsaves it, **then** its state is reflected in the favorites view.
- **Given** several eligible recipes, **when** the user requests another suggestion, **then** the app presents a different eligible candidate while preserving the same safety and tool constraints. The ordering rule still needs a design decision.

### Candidate feature — Understand proposed recipe adjustments

**As a** user missing an ingredient, **I want** any proposed substitution or serving adjustment clearly separated from the original recipe, **so that** I can judge the change before cooking.

- **Given** an adjustment is available, **when** the recipe detail opens, **then** the changed ingredient or amount is labeled as a suggestion and the original value remains visible.
- **Given** an allergy-related ingredient, an essential ingredient without an approved substitute, or a food-safety-critical step, **when** an adjustment is considered, **then** the app does not apply an unsupported change.

This is not yet a mandatory user story. The allowed substitution list, whether an external AI model may propose a candidate, and the approval method remain design decisions. The product must not claim an unverified substitute is safe. A separate candidate is a suggestion that one additional ingredient would unlock more meals. A seasoning checklist for ingredients that photos cannot reliably reveal is also under consideration.

## Non-functional Requirements

| ID | Requirement | How the team will check it |
| --- | --- | --- |
| NFR-01 | Safety claims must be limited to ingredients with reliable allergen metadata. Unknown metadata must not be presented as verified safe. | Review recommendation outputs with known conflict and unknown-metadata cases. |
| NFR-02 | Users must be able to correct recognition output before it changes their stored ingredient list. | Complete photo, correction, removal, and manual-entry flows. |
| NFR-03 | Recipe details must preserve source attribution and distinguish original instructions from suggested changes. | Inspect every recipe-detail state in the curated set. |
| NFR-04 | API credentials must stay on the server and must not be embedded in the Android application. | Review build configuration and network architecture. |
| NFR-05 | The application must communicate loading, empty-result, and recoverable error states in plain language. | Exercise each state in an integrated build. |
| NFR-06 | Photo-to-confirmation and recipe-result response times should be measured on the deployment setup; numerical targets will be set after a real-image baseline. | Record latency on representative devices and images in a later iteration. |

## User Interface Requirements

The flow below summarizes intended transitions and failure paths. It is based on the current Android screen structure and [team Figma design](https://www.figma.com/design/bxDeYMiAzC9LY7oHNj2OQV/my-little-chef?t=4IKrs5VSkKNKfJMZ-1).

```mermaid
flowchart LR
    A[Onboarding / Profile] --> B[Digital Fridge]
    B --> C[Camera / Gallery]
    C --> D[Review Ingredient Candidates]
    D -->|Confirm and save| B
    D -->|Failure or no candidates| E[Retry / Manual Entry]
    E --> B
    B --> F[Recipe Results]
    F --> G[Recipe Detail]
    F -->|Another result| F
    G --> H[Favorites]
```

| Screen | Allowed user input and action | Next screen or failure handling |
| --- | --- | --- |
| Onboarding/Profile | Nickname, cooking tools, allergies; save/edit | Digital refrigerator; show validation for invalid or missing required input |
| Digital Refrigerator | View, add, remove confirmed ingredients; start capture | Camera/gallery or manual add; show empty-inventory guidance |
| Camera/Gallery | Capture or choose an image; submit | Recognition review; show permission, upload, and analysis errors |
| Recognition Review | Confirm, remove, or add ingredient candidates | Digital refrigerator; show retry/manual entry for zero candidates |
| Recipe Results | Inspect labels, filter/sort, refresh, save | Recipe detail; show no-feasible-recipe explanation |
| Recipe Detail | Read source, amounts, steps, missing items, adjustments | Back to results; clearly separate original and suggested content |
| Favorites | Open or remove saved recipes | Recipe detail; show an empty-favorites state |

## Iteration 2 Scope and Requirement Status

![Current UI flow and failure paths](images/flow-iter2.svg)

The original stories above describe the completed product. They are not all delivered in Iteration2. No UAT stories are newly frozen by this revision.

| Requirement | Current implementation | Remaining limitation / evidence |
| --- | --- | --- |
| US01 | Profile/tools/allergies persist through the existing DataStore repository | Tools/allergies do not yet affect filtering; suitability is explicitly unverified |
| US02 | Photo candidates remain separate until confirmation; users can edit/remove/add; retry/manual input remain available | Automated network/render and manual live device evidence; not a recognition-accuracy claim |
| US03 | Name persistence, normalization/deduplication and repository deletion | Repository/file-reopen tests cover state; a full UI deletion acceptance result is not claimed |
| US04 | Canonical ID filtering, missing counts, sorting and explicit empty/error/partial states | No complete allergy/tool filtering; counts exclude seasonings while full absent list includes them |
| US05 | Original quantities/servings/steps/tips and clearly separated suggestions | No authoritative one-serving conversion; new source data has no URL field, so original-source attribution URL remains a gap |
| US06 | Favorite IDs persist, originals restore without AI and sort modes work | No guarantee of a different eligible recipe on refresh; prior AI suggestions are not persisted |
| Candidate adjustment | AI can suggest or refuse changes; original always retained | Structural output validity is not semantic/food-safety verification |
| NFR01/03 | Unverified suitability is disclosed; originals and suggestions separated | Reliable allergen metadata and source URLs still unavailable |
| NFR02/04/05 | User confirmation, server-only credentials, separate states | Client cancellation cannot cancel an already running synchronous provider request |
| NFR06 | Explicit request timeout budget and recorded device/provider runs | No general numerical latency target or population-level usability claim yet |

Iteration2 test mapping and results are on the separate Testing Documentation page. Docker/nginx/deployment work is deferred to Iteration3 preparation by user scope decision. Existing Sheet P3/P4/P25/P26 and P27–P35 are compared read-only; actual schedule edits and official publication/submission remain user actions.
