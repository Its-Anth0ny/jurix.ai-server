import json
from typing import Dict, Any

from app.core.llm import call_llm


TRANSLATION_PROMPT = """You are a legal document translator. Translate the string values in the following JSON to {target_lang}.

Rules:
- Translate only string values. Do not translate or rename JSON keys.
- Preserve all data types: numbers, booleans, arrays, and nested objects must remain unchanged.
- If a value is already in {target_lang}, leave it as-is.
- Legal terms, proper nouns (names, courts, case numbers), and citations must be preserved exactly.
- Return ONLY the translated JSON object. No explanations, no markdown, no code blocks.

Input JSON:
{output}"""


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
