from __future__ import annotations
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class RecipeCategory(str, Enum):
    MAIN = "주식"          # 메인 요리 / 식사 (찌개, 볶음밥, 덮밥, 탕 등)
    SIDE = "부식"          # 반찬 / 사이드 (계란말이, 조림, 무침, 볶음 등)
    CONDIMENT = "양념/소스" # 양념장, 디핑소스, 드레싱 등

class IngredientRole(str, Enum):
    CORE = "CORE"      # 주재료 (단백질/주탄수화물: 돼지고기, 두부, 닭고기, 밥 등)
    SUB = "SUB"        # 부재료 (채소, 버섯: 대파, 양파, 버섯, 당근 등)
    PANTRY = "PANTRY"  # 상비 조미료/양념 (간장, 식용유, 고춧가루, 참기름, 소금 등)

class RawDetection(BaseModel):
    name: str
    confidence: float = Field(ge=0.0, le=1.0)
    bbox: Optional[List[int]] = None  # [ymin, xmin, ymax, xmax] - only in P0 Baseline

class CanonicalIngredient(BaseModel):
    id: int
    name: str
    role: IngredientRole
    category: str
    standard_unit: str
    allergens: List[str] = Field(default_factory=list)  # Direct $O(1)$ allergen attribute
    confusables: List[str] = Field(default_factory=list) # Sibling confusable names (e.g. 국간장 vs 진간장)

class RecipeIngredient(BaseModel):
    ingredient_id: int
    name: str
    amount: float
    unit: str
    role: IngredientRole

class RecipeStep(BaseModel):
    step_number: int
    instruction: str
    duration_minutes: int

class Recipe(BaseModel):
    id: int
    title: str
    source: str
    category: RecipeCategory
    base_servings: int = 2
    cooking_time_minutes: int
    allergens: List[str] = Field(default_factory=list)
    ingredients: List[RecipeIngredient]
    steps: List[RecipeStep]

class BenchmarkMetric(BaseModel):
    pipeline_name: str
    scenario_name: str
    total_latency_ms: float
    vision_latency_ms: float
    matching_latency_ms: float
    recommendation_latency_ms: float
    estimated_tokens: int
    canonical_recall: float
    confusable_accuracy: float
    oov_rejection_rate: float
    hallucination_rate: float = 0.0
    condiment_spam_rate: float
    top1_is_main_dish: bool
    core_dinner_utility: float = 1.0
    allergen_violation_count: int
    summary: str
    details: Dict[str, Any] = Field(default_factory=dict)
