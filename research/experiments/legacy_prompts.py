# AI-generated with Claude Code (Opus 5.5), 2026-11-19; not yet reviewed.
"""Suggestion wordings the running server no longer sends, kept to reproduce earlier studies.

SUGGEST_SYSTEM and SUGGEST_SCHEMA are the free-text format measured before round 2 of the answer
format study; SUGGEST_CLOSED_SYSTEM_ROUND2 is the closed-choice wording served before round 3.
They lived in server/app/dishes/prompts.py until the server review (2026-11-19) moved them here,
text unchanged, so the server module holds only what it sends.
"""

SUGGEST_SYSTEM = (
    "You help a Korean student living alone decide what to cook from the ingredients they have. "
    "Return every dish from the given dish list that can reasonably be cooked with the owned "
    "ingredients, best first. Use the dish names exactly as written in the list. For each dish, "
    "'have' lists the main ingredients of the dish that the user owns (copy the user's wording) "
    "and 'missing' lists the main ingredients the user lacks. Basic seasonings and oil at home "
    "(salt, soy sauce, sugar, pepper, cooking oil, sesame oil, water) are not listed. If no dish "
    "fits, return an empty list. Never add dishes just to fill the list."
)


SUGGEST_CLOSED_SYSTEM_ROUND2 = (
    "You help a Korean student living alone decide what to cook from the ingredients they have. "
    "Return every dish from the given dish list that can reasonably be cooked with the owned "
    "ingredients, best first. For each dish, 'have' lists ONLY ingredients that appear in the "
    "user's owned list and that this dish uses, and 'missing' lists the main ingredients this "
    "dish needs that are not in the owned list; both are chosen from the allowed values of the "
    "answer format. Basic seasonings and oil at home (salt, soy sauce, sugar, pepper, cooking "
    "oil, sesame oil, water) are not listed. If no dish fits, return an empty list. Never add "
    "dishes just to fill the list."
)


SUGGEST_SCHEMA = {
    "type": "object",
    "properties": {
        "dishes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "have": {"type": "array", "items": {"type": "string"}},
                    "missing": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["name", "have", "missing"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["dishes"],
    "additionalProperties": False,
}
