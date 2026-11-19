# ADR 001: Small roles and one composition root for the dish services

- **Status:** Accepted (2026-11-19)

## Context

The dish services call a model, YouTube and three kinds of stored data (dish list, recipes, video lists). Before this change `DishService` built its own `Reviser`, `VideoFinder` built its own HTTP calls, cache and store, and `service.py` held the prompts, the schemas and the answer checks. A change of wording, of video policy or of model provider meant editing the same few files, and a test of the service needed real HTTP clients or monkeypatching.

## Decision

- Split by reason to change (SRP): `prompts.py` (what the model is asked), `answers.py` (checking what it answered), `llm.py` (the model client), `youtube.py` (verifying videos), `video_search.py` (proposing videos), `video_store.py` and `videos.py` (stored videos, the cache and the lookup that coordinates them), `recipes.py`, `revision.py` (coordinates one revision) with `revision_check.py` (its rules), `catalog.py`. `service.py` and `router.py` only coordinate.
- Services depend on narrow roles (`typing.Protocol` in `roles.py`): `ChatModel`, `VideoSource`, `VideoVerifier`, `StoredVideos`, `RecipeBook`, `DishCatalog`, `IngredientIndex`. No role has a method that an implementation must stub out (ISP).
- The concrete classes are created in one place, `dependencies.py` (`build_dish_parts`), from the environment, and passed in through constructors (DIP). The routes get their own part from one `DishParts` bundle (service, reviser, ingredient index), so the dish service does not carry objects only the router uses (server review, 2026-11-19). Nothing is built at import time. The in-memory video cache is one `VideoCache` object made at app start and passed to the finder, not a module-level global.
- Each role has one abstract contract test (`server/tests/dishes/contracts/`); the real class (with a fake transport) and a hand-written fake must both pass it (LSP).

## Consequences

- A test hands in fakes; no test patches a module.
- Changing the request wording, the video policy or a rule of the revision check touches one module.
- More files (about twenty in `app/dishes`) and one indirection for the reader: to see what runs in production, read `dependencies.py`.

## Not now

- No Abstract Factory and no dependency-injection framework: one function that builds the objects is enough while there is one model provider and one video source.
- No interface for classes that have one implementation and no reason to change (for example the schemas).
- No service locator or registry of roles.
