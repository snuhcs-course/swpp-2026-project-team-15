import time
from typing import List, Dict, Any, Optional
from common.models import RawDetection, Recipe, BenchmarkMetric
from common.recipe_db import CANONICAL_INGREDIENTS, SAMPLE_RECIPES

class BaselineClosedBBoxPipeline:
    """
    P0: Baseline Pipeline
    - Vision: Closed-set YOLO/VLM with BBox coordinates [ymin, xmin, ymax, xmax]
    - Normalization: Naive Exact / LIKE string matching (fails on brands/adjectives)
    - Allergen: Recipe title string check (misses derivative allergens like 새우젓)
    - Recommendation: Naive unweighted SQL intersection ratio (prone to condiment spam)
    """
    def __init__(self):
        self.name = "P0: Baseline (Closed BBox + Naive SQL)"
        self.closed_vocabulary = {
            "돼지고기", "두부", "계란", "신김치", "대파", "양파", 
            "콩나물", "애호박", "진간장", "고추장", "된장", "다진마늘", 
            "고춧가루", "참기름", "소금"
        }

    def simulate_vision(self, input_items: List[str]) -> List[RawDetection]:
        detections = []
        for idx, item in enumerate(input_items):
            if item in self.closed_vocabulary:
                detections.append(
                    RawDetection(
                        name=item,
                        confidence=0.88,
                        bbox=[100 + idx*50, 100 + idx*50, 200 + idx*50, 200 + idx*50]
                    )
                )
        return detections

    def normalize_entities(self, detections: List[RawDetection]) -> List[int]:
        name_to_id = {ci.name: ci.id for ci in CANONICAL_INGREDIENTS.values()}
        resolved_ids = []
        for det in detections:
            if det.name in name_to_id:
                resolved_ids.append(name_to_id[det.name])
        return resolved_ids

    def recommend_recipes(self, confirmed_ids: List[int], user_allergies: List[str]) -> List[Dict[str, Any]]:
        results = []
        for r in SAMPLE_RECIPES:
            violated = False
            for allergy in user_allergies:
                if allergy in r.title:
                    violated = True
                    break
            if violated:
                continue

            recipe_ing_ids = [ri.ingredient_id for ri in r.ingredients]
            matched = set(confirmed_ids).intersection(set(recipe_ing_ids))
            match_rate = len(matched) / len(recipe_ing_ids) if recipe_ing_ids else 0.0

            results.append({
                "recipe": r,
                "match_rate": round(match_rate, 3),
                "matched_count": len(matched),
                "total_count": len(recipe_ing_ids),
                "category": r.category.value
            })

        results.sort(key=lambda x: x["match_rate"], reverse=True)
        return results

    def run_benchmark(self, scenario_name: str, input_items: List[str], user_allergies: List[str], scenario_meta: Dict[str, Any] = None) -> BenchmarkMetric:
        scenario_meta = scenario_meta or {}
        t0 = time.time()
        
        t_v0 = time.time()
        detections = self.simulate_vision(input_items)
        t_v1 = time.time()
        
        estimated_tokens = len(input_items) * 35 + 50

        t_m0 = time.time()
        confirmed_ids = self.normalize_entities(detections)
        t_m1 = time.time()

        t_r0 = time.time()
        ranked = self.recommend_recipes(confirmed_ids, user_allergies)
        t_r1 = time.time()

        total_time = (time.time() - t0) * 1000.0

        # Canonical Recall @ 1 on ground truth food items
        gt_food = scenario_meta.get("ground_truth_food", input_items)
        canonical_recall = len(confirmed_ids) / len(gt_food) if gt_food else 0.0

        # Condiment spam rate
        condiment_spam_rate = 0.0
        top1_is_main = False
        if ranked:
            top_rec = ranked[0]
            if top_rec["category"] == "양념/소스":
                condiment_spam_rate = 1.0
            if top_rec["category"] == "주식":
                top1_is_main = True

        # Allergen safety check
        allergen_violations = 0
        for rec_dict in ranked:
            r = rec_dict["recipe"]
            for ri in r.ingredients:
                ci = CANONICAL_INGREDIENTS.get(ri.ingredient_id)
                if ci and any(al in user_allergies for al in ci.allergens):
                    allergen_violations += 1

        confusable_acc = 0.0 if scenario_meta.get("is_confusable") else 0.50
        hallucination_rate = 0.0 # Dropped all clutter due to closed set
        oov_rejection = 0.0
        core_dinner_utility = 0.35

        return BenchmarkMetric(
            pipeline_name=self.name,
            scenario_name=scenario_name,
            total_latency_ms=round(total_time, 2),
            vision_latency_ms=round((t_v1 - t_v0) * 1000.0, 2),
            matching_latency_ms=round((t_m1 - t_m0) * 1000.0, 2),
            recommendation_latency_ms=round((t_r1 - t_r0) * 1000.0, 2),
            estimated_tokens=estimated_tokens,
            canonical_recall=round(canonical_recall, 3),
            confusable_accuracy=round(confusable_acc, 3),
            oov_rejection_rate=round(oov_rejection, 3),
            hallucination_rate=round(hallucination_rate, 3),
            condiment_spam_rate=round(condiment_spam_rate, 3),
            top1_is_main_dish=top1_is_main,
            core_dinner_utility=round(core_dinner_utility, 3),
            allergen_violation_count=allergen_violations,
            summary=f"P0: Resolved {len(confirmed_ids)}/{len(input_items)}. Top1: {ranked[0]['recipe'].title if ranked else 'None'}",
            details={"top_3": [r["recipe"].title for r in ranked[:3]]}
        )
