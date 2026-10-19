"""Fixed experiment inputs; these are not filtering or product-selection rules."""
# AI-generated initial importer with Codex (GPT-6.1 Sol)
# 2026-10-14 to 2026-10-16; reviewed and revised by Soohyun An

from dataclasses import dataclass

RECIPES = (
    (9, "오므라이스"), (18, "두부국"), (97, "계란말이"), (112, "김치적"),
    (114, "두부김치"), (115, "오믈렛"), (118, "중국식볶음밥"), (130, "두부양념조림"),
    (192, "김치채소쌈"), (194, "계란말이주먹밥"), (216, "두부오믈렛"), (238, "김치주먹밥"),
    (291, "김치쌈밥"), (299, "열무비빔밥"), (320, "김치볶음밥"), (421, "양파전"),
)
E0 = ((70, "김치"), (223, "밥"), (32, "계란"), (284, "소금"),
      (282, "설탕"), (313, "식용유"), (554, "후추"))
E1  = E0 + ((345, "양파"), (9, "간장"), (147, "두부"))
GARLIC_RECIPES = ((335, "마늘빵"), (395, "어묵볶음"), (97, "계란말이"), (421, "양파전"))
GARLIC_BASE = E1 + ((214, "바게트"), (349, "어묵"), (213, "밀가루"))
INVENTORIES = {"AI-E0": E0, "AI-E1": E1,
               "AI-E2": GARLIC_BASE + ((169, "마늘"),),
               "AI-E3": GARLIC_BASE + ((103, "다진마늘"),)}
EXPERIMENT_RECIPES = {"AI-E0": RECIPES, "AI-E1": RECIPES,
                      "AI-E2": GARLIC_RECIPES, "AI-E3": GARLIC_RECIPES}
ALL_RECIPES = tuple(dict(RECIPES + GARLIC_RECIPES).items())


@dataclass(frozen=True)
class Case:
    """A stable experiment/recipe key, independent of expected feasibility."""

    experiment: str
    recipe_id: int

    @property
    def case_id(self) -> str:
        return f"{self.experiment}-{self.recipe_id}"


def matrix(experiments: tuple[str, ...] = ("AI-E0", "AI-E1")) -> tuple[Case, ...]:
    """Build selected condition matrices; preserve the original 32-case default."""
    return tuple(Case(experiment, recipe_id) for experiment in experiments
                 for recipe_id, _ in EXPERIMENT_RECIPES[experiment])
