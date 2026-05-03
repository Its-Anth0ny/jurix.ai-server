import json
from typing import Dict, Any

from app.core.llm import call_llm


TRANSLATION_PROMPT = """Translate the following JSON output to {target_lang}.

Return ONLY valid JSON (the translated version of the input). No explanations, no markdown, no code blocks.
Return ONLY the translated JSON. Do not wrap in code blocks or add any commentary.

Input JSON:
{output}
"""


def translate_output(output: Dict[str, Any], target_lang: str = "en") -> Dict[str, Any]:
    """
    Translate JSON output to target language using LLM.

    Args:
        output: Output dict to translate
        target_lang: Target language code (e.g., "en", "es", "fr")

    Returns:
        Translated output dict, or original on failure
    """
    try:
        output_json = json.dumps(output, ensure_ascii=False)
        prompt = TRANSLATION_PROMPT.format(target_lang=target_lang, output=output_json)
        result = call_llm(prompt)
        if "error" in result:
            return output
        return result
    except Exception:
        return output
