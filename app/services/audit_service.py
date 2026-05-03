import json
from typing import Dict, Any

from app.core.llm import call_llm, LLMError


AUDIT_PROMPT = """You are a legal audit validator. Cross-check the action plan against the extracted facts.

Identify any hallucinations, unsupported claims, or inconsistencies between the action plan and the facts.

Return ONLY valid JSON matching this schema exactly:
{{
    "status": "approved" or "needs_review",
    "issues": ["issue 1", "issue 2"] or empty list if approved
}}

Return ONLY valid JSON. No explanations, no markdown, no code blocks.

Extracted facts:
{facts}

Action plan:
{action_plan}
"""


def audit_action_plan(
    extraction: Dict[str, Any],
    action_plan: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Audit action plan against extracted facts.

    Args:
        extraction: Structured extraction
        action_plan: Generated action plan

    Returns:
        Audit result dict

    Raises:
        LLMError: If audit fails
    """
    facts_json = json.dumps(extraction, indent=2)
    action_json = json.dumps(action_plan, indent=2)
    prompt = AUDIT_PROMPT.format(facts=facts_json, action_plan=action_json)
    return call_llm(prompt)
