# AI-generated with Claude Code (Opus 5.5), 2026-11-19; reviewed by Jaehyuk Choi.
from app.dishes.recipes import CREDIT_SECONDS, CreditedRecipes, RecipeStore
from app.dishes.schemas import SourceRecipe
from tests.dishes.contracts.fakes import FakeVideoVerifier
from tests.dishes.test_revision import RECIPE


class CountingVerifier(FakeVideoVerifier):
    def __init__(self, usable, **kw):
        super().__init__(usable, **kw)
        self.calls = 0

    def check(self, ids):
        self.calls += 1
        return super().check(ids)


def stored(title="", channel=""):
    raw = {**RECIPE, "video": {"id": "abcdefghijk", "title": title, "channel": channel}}
    return RecipeStore({"kimchi-fried-rice": SourceRecipe.model_validate(raw)})


def test_credit_comes_from_youtube_not_from_the_file():
    book = CreditedRecipes(stored("old title", "old channel"), FakeVideoVerifier({"abcdefghijk"}))
    video = book.get("kimchi-fried-rice").video
    assert (video.id, video.title, video.channel) == ("abcdefghijk", "t", "c")


def test_gone_or_failed_video_leaves_the_credit_empty_but_keeps_the_recipe():
    gone = CreditedRecipes(stored("x", "y"), FakeVideoVerifier(set()))
    assert gone.get("kimchi-fried-rice").video.title == ""
    down = CreditedRecipes(stored("x", "y"), FakeVideoVerifier(set(), fail=True))
    recipe = down.get("kimchi-fried-rice")
    assert recipe.video.title == "" and recipe.steps


def test_credit_is_reused_for_a_day_then_looked_up_again():
    now = [0.0]
    verifier = CountingVerifier({"abcdefghijk"})
    book = CreditedRecipes(stored(), verifier, clock=lambda: now[0])
    book.get("kimchi-fried-rice")
    book.get("kimchi-fried-rice")
    assert verifier.calls == 1
    now[0] = CREDIT_SECONDS + 1
    book.get("kimchi-fried-rice")
    assert verifier.calls == 2


def test_a_failed_lookup_is_not_cached():
    verifier = CountingVerifier(set(), fail=True)
    book = CreditedRecipes(stored(), verifier)
    book.get("kimchi-fried-rice")
    book.get("kimchi-fried-rice")
    assert verifier.calls == 2
