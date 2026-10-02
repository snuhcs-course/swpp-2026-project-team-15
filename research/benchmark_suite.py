import json
import time
from pathlib import Path
from typing import List, Dict, Any
from fastembed import TextEmbedding

from pipelines.baseline_closed_bbox import BaselineClosedBBoxPipeline
from pipelines.p1_open_vocab_embedding import UserProposedPipeline
from pipelines.p2_hypothesis_driven_vision import LearnedContrastiveMetricPipeline
from pipelines.p3_role_gated_recommender import ThresholdGatedSafetyPipeline
from pipelines.p4_constraint_action_dag import LexicographicalUtilityPipeline
from pipelines.p5_integrated_metric_dag import IntegratedMetricDAGPipeline

SCENARIOS = [
    {
        "id": "scenario_1_typical_meal",
        "name": "1. Standard Single-Person Fridge",
        "description": "Standard home inventory evaluating basic dinner meal recommendation.",
        "input_items": ["돼지고기", "신김치", "두부", "대파", "다진마늘"],
        "user_allergies": [],
        "meta": {"is_pantry_heavy": False, "is_confusable": False}
    },
    {
        "id": "scenario_2_condiment_spam",
        "name": "2. Condiment-Heavy / Pantry Spam Stress Test",
        "description": "Pantry-only inventory testing whether dipping sauces spam the top recommendation.",
        "input_items": ["진간장", "식초", "설탕", "다진마늘", "참기름"],
        "user_allergies": [],
        "meta": {"is_pantry_heavy": True, "is_confusable": False}
    },
    {
        "id": "scenario_3_allergen_safety",
        "name": "3. Derivative Allergen Safety Challenge",
        "description": "User with Crustacean (갑각류) allergy; tests whether hidden fermented 새우젓 is caught.",
        "input_items": ["계란", "대파", "새우젓", "두부"],
        "user_allergies": ["갑각류"],
        "meta": {"is_pantry_heavy": False, "is_confusable": False}
    },
    {
        "id": "scenario_4_noisy_brands",
        "name": "4. Visual Modifiers & Open-Vocab Brand Stress Test",
        "description": "Real grocery packaging mentions with brand names, weights, and packaging terms.",
        "input_items": ["제주산 흑돼지 삼겹살 500g", "비비고 썰은배추김치 400g", "백설 진간장 금F", "CJ 부침용 단단한두부", "손질 흙대파 한단"],
        "user_allergies": [],
        "meta": {"is_pantry_heavy": False, "is_confusable": False}
    },
    {
        "id": "scenario_5_confusables",
        "name": "5. Fine-Grained Sibling Confusables Stress Test",
        "description": "Linguistic culinary siblings that generic pre-trained SBERT confuses (국간장 vs 진간장, 단호박 vs 애호박).",
        "input_items": ["백설 맑은 국간장 500ml", "달콤한 미니 단호박 1통", "청정원 남해안 멸치액젓"],
        "user_allergies": [],
        "meta": {
            "is_pantry_heavy": False,
            "is_confusable": True,
            "ground_truth_confusables": {
                "백설 맑은 국간장 500ml": 41,
                "달콤한 미니 단호박 1통": 26,
                "청정원 남해안 멸치액젓": 52
            }
        }
    },
    {
        "id": "scenario_6_oov_noise",
        "name": "6. Open-World Clutter & Non-Food Hallucination Stress Test",
        "description": "Visual scene containing non-food household items, plastic wrap, and a single valid food item.",
        "input_items": ["삼성 스마트 TV 리모컨", "크린랩 롤 비닐백", "깨끗한 물티슈 100매", "신선 계란 10구"],
        "user_allergies": [],
        "meta": {
            "is_pantry_heavy": False,
            "is_confusable": False,
            "non_food_items": ["삼성 스마트 TV 리모컨", "크린랩 롤 비닐백", "깨끗한 물티슈 100매"],
            "ground_truth_food": ["신선 계란 10구"]
        }
    }
]

def run_suite():
    print("[Initializing Shared Multilingual FastEmbed Model...]")
    t0 = time.time()
    shared_embed = TextEmbedding(model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
    print(f"[Model Ready in {time.time() - t0:.2f}s]")

    pipelines = [
        BaselineClosedBBoxPipeline(),
        UserProposedPipeline(shared_embed),
        LearnedContrastiveMetricPipeline(shared_embed),
        ThresholdGatedSafetyPipeline(shared_embed),
        LexicographicalUtilityPipeline(shared_embed),
        IntegratedMetricDAGPipeline(shared_embed),
    ]

    all_results = []

    print("\n" + "="*80)
    print("STARTING PAPER-LEVEL TARGETED BENCHMARK SUITE (Zero Magic Numbers & Learned Metric)")
    print("="*80)

    for scenario in SCENARIOS:
        print(f"\n>>> Scenario: {scenario['name']} ({len(scenario['input_items'])} items, Allergies: {scenario['user_allergies']})")
        
        scenario_metrics = []
        for p in pipelines:
            metric = p.run_benchmark(
                scenario_name=scenario["name"],
                input_items=scenario["input_items"],
                user_allergies=scenario["user_allergies"],
                scenario_meta=scenario["meta"]
            )
            scenario_metrics.append(metric.model_dump())
            print(f"  [{p.name.split(':')[0]}] {metric.summary} | Lat: {metric.total_latency_ms}ms | Recall: {metric.canonical_recall*100:.0f}% | Sibling: {metric.confusable_accuracy*100:.0f}% | Hallucination: {metric.hallucination_rate*100:.0f}% | CoreUtil: {metric.core_dinner_utility:.2f}")

        all_results.append({
            "scenario_id": scenario["id"],
            "scenario_name": scenario["name"],
            "description": scenario["description"],
            "input_items": scenario["input_items"],
            "user_allergies": scenario["user_allergies"],
            "metrics": scenario_metrics
        })

    output_path = Path(__file__).parent / "benchmark_results.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)

    print(f"\n[Saved Paper-Level Benchmark Results to: {output_path}]")

if __name__ == "__main__":
    run_suite()
