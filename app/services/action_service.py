from typing import Dict, Any

from app.core.llm import call_llm, LLMError


ACTION_PLAN_PROMPT = """You are a legal action planner. Based ONLY on the extracted facts provided, generate an action plan.

Use ONLY the information in the extracted facts. Do not add external knowledge or make assumptions.

Return ONLY valid JSON matching this schema exactly:
{{
    "decision": "comply" or "appeal",
    "actions": [
        {{
            "action": "specific action description",
            "deadline": "deadline date or null",
            "responsible_party": "party responsible or null"
        }}
    ],
    "department": "responsible department or empty string",
    "deadlines": ["deadline 1", "deadline 2"] or empty list
}}

Return ONLY valid JSON. No explanations, no markdown, no code blocks.

Extracted facts:
{facts}
"""


def generate_action_plan(extraction: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate action plan from extracted facts.

    Args:
        extraction: Structured extraction from extraction_service

    Returns:
        Action plan dict

    Raises:
        LLMError: If generation fails
    """
    import json
    facts_json = json.dumps(extraction, indent=2)
    prompt = ACTION_PLAN_PROMPT.format(facts=facts_json)
    return call_llm(prompt)