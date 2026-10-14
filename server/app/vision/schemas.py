# AI-generated with Claude Code (Opus 5.5), 2026-10-11 to 2026-10-14; reviewed by Jaehyuk Choi.
from sqlmodel import Field, SQLModel


class DetectedItem(SQLModel):
    """One item a vision provider reports; mirrors the 2026-09-30 Gemini benchmark output."""

    name_raw: str
    category: str
    confidence: float = Field(ge=0.0, le=1.0)


class IngredientCandidate(SQLModel):
    name: str = Field(description="Generic ingredient name used for recipe matching")
    raw_texts: list[str] = Field(description="Labels or descriptions seen in the photo")
    confidence: float = Field(description="Highest model confidence among merged items, 0-1")


class AnalyzeResponse(SQLModel):
    """Unconfirmed candidates: the user must review them before they enter the fridge."""

    candidates: list[IngredientCandidate]
