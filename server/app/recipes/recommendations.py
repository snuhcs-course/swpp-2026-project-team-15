"""Filter the full catalog and attempt a bounded, request-local Revision plan."""
# AI-generated with Codex(GPT-6.1 Sol)
# 2026-10-17; reviewed by Soohyun An

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor

from app.recipes.policy import DEFAULT_POLICY, RecommendationPolicy
from app.recipes.providers import MockRevisionLLM
from app.recipes.schemas import (
    FilteringCounts,
    RecipeRevision,
    RecommendationEntry,
    RecommendationsRequest,
    RecommendationsResponse,
    RevisionError,
    RevisionSummary,
)
from app.recipes.service import RecipeRepository
from recipe_revision.core import LLM
from recipe_revision.failures import Failure
from recipe_revision.pipeline import Steps, revise_with_steps
from recipe_revision.prescreen import prescreen_refusal


class InvalidRevisionLimit(ValueError):
    """The requested attempt count exceeds the server's configured limit."""


def public_error(failure: Failure) -> RevisionError:
    """Build a public error from allowlisted metadata, never exception messages."""
    return RevisionError(
        code=failure.code,
        stage=failure.stage,
        http_status=failure.http_status,
        message=failure.message,
        scope=failure.scope,
    )


class RecommendationService:
    """Keep source loading, candidate selection and independent AI calls separate."""

    def __init__(
        self,
        repository: RecipeRepository,
        *,
        policy: RecommendationPolicy = DEFAULT_POLICY,
        llm_factory: Callable[[], LLM] = MockRevisionLLM,
    ):
        self.repository, self.policy, self.llm_factory = repository, policy, llm_factory

    def recommend(self, request: RecommendationsRequest) -> RecommendationsResponse:
        """Return every candidate, with at most n model attempts and no retry."""
        limit = (
            self.policy.default_revision_limit
            if "revision_limit" not in request.model_fields_set
            else request.revision_limit
        )
        if limit > self.policy.maximum_revision_limit:
            raise InvalidRevisionLimit("Revision limit exceeds the configured maximum")
        sources, inventory = self.repository.load_catalog(
            request.ingredient_ids, self.policy.water_id
        )
        available = frozenset(row.ingredient_id for row in inventory)
        entries = []
        for source in sources:
            metrics = self.policy.metrics(source, available)
            if self.policy.accepts(metrics):
                entries.append(
                    RecommendationEntry(
                        recipe_id=source.recipe_id,
                        original=source,
                        filtering=FilteringCounts(
                            matched_count=metrics.total_matches,
                            missing_count=metrics.total_ingredients - metrics.total_matches,
                            main_matched_count=metrics.main_matches,
                        ),
                        revision=RecipeRevision(
                            status="not_attempted", not_attempted_reason="outside_revision_limit"
                        ),
                    )
                )
        # Sorting a separate plan avoids giving API array order display semantics.
        ordered = sorted(
            entries,
            key=lambda entry: (
                entry.filtering.missing_count,
                -entry.filtering.matched_count,
                entry.recipe_id,
            ),
        )
        selected = ordered[:limit]
        if self.policy.prescreen == "fill":
            # Candidates refused without a model call do not use up the limit: walk down the ranking
            # until ``limit`` candidates need the model (selected_count can then exceed the limit).
            selected, needing_model = [], 0
            for entry in ordered:
                selected.append(entry)
                refused = prescreen_refusal(
                    entry.original, inventory, seasonings=self.policy.seasonings
                )
                needing_model += refused is None
                if needing_model == limit:
                    break
        summary = RevisionSummary(limit=limit, selected_count=len(selected), attempted_count=0)
        response = RecommendationsResponse(
            recipes=entries,
            revision_summary=summary,
            assumed_ingredient_ids=self.policy.assumed_ids,
        )
        if not selected:
            return response
        try:
            llm = self.llm_factory()
        except Exception:
            summary.stopped_error = public_error(Failure("configuration", "configuration"))
            for entry in selected:
                entry.revision = RecipeRevision(
                    status="not_attempted", not_attempted_reason="shared_failure"
                )
            return response
        steps = Steps(
            prescreen=self.policy.prescreen != "off",
            retry=self.policy.retry_on_rejection,
            complete_changes=self.policy.complete_changes,
            seasonings=self.policy.seasonings,
        )

        def attempt(entry: RecommendationEntry) -> RecipeRevision:
            """One independent revision call; never raises."""
            try:
                outcome = revise_with_steps(entry.original, inventory, llm, steps)
                if outcome.status in ("revised", "refused"):
                    return RecipeRevision(status=outcome.status, result=outcome.model_result)
                failure = outcome.failure or Failure("api_error", "api_request")
            except Exception:
                failure = Failure("internal", "revision")
            return RecipeRevision(status="failed", error=public_error(failure))

        workers = min(self.policy.revision_workers, len(selected))
        attempts = None
        if workers > 1:
            with ThreadPoolExecutor(max_workers=workers) as pool:
                attempts = list(pool.map(attempt, selected))
        for index, entry in enumerate(selected):
            if summary.stopped_error is not None:
                entry.revision = RecipeRevision(
                    status="not_attempted", not_attempted_reason="shared_failure"
                )
                continue
            summary.attempted_count += 1
            entry.revision = attempts[index] if attempts else attempt(entry)
            error = entry.revision.error
            if error is not None and error.scope == "shared":
                summary.stopped_error = error
        return response
