"""Filter the full catalog and attempt a bounded, request-local Revision plan."""
# AI-generated with Codex(GPT-6.1 Sol)
# 2026-10-17; reviewed by Soohyun An

from collections.abc import Callable

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
from recipe_revision.core import LLM, revise
from recipe_revision.failures import Failure


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
        """Return every candidate, with at most n sequential attempts and no retry."""
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
        selected = sorted(
            entries,
            key=lambda entry: (
                entry.filtering.missing_count,
                -entry.filtering.matched_count,
                entry.recipe_id,
            ),
        )[:limit]
        summary = RevisionSummary(limit=limit, selected_count=len(selected), attempted_count=0)
        response = RecommendationsResponse(
            recipes=entries,
            revision_summary=summary,
            assumed_ingredient_ids=[self.policy.water_id],
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
        for entry in selected:
            if summary.stopped_error is not None:
                entry.revision = RecipeRevision(
                    status="not_attempted", not_attempted_reason="shared_failure"
                )
                continue
            summary.attempted_count += 1
            try:
                outcome = revise(entry.original, inventory, llm)
                if outcome.status in ("revised", "refused"):
                    entry.revision = RecipeRevision(
                        status=outcome.status, result=outcome.model_result
                    )
                    continue
                failure = outcome.failure or Failure("api_error", "api_request")
            except Exception:
                failure = Failure("internal", "revision")
            error = public_error(failure)
            entry.revision = RecipeRevision(status="failed", error=error)
            if error.scope == "shared":
                summary.stopped_error = error
        return response
