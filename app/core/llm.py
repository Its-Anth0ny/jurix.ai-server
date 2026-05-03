import json
import logging
import re
from typing import Optional, Dict, Any
import requests

from app.core.config import settings


class LLMError(Exception):
    """Raised when LLM call fails after retries."""
    pass


logger = logging.getLogger(__name__)

# Minimal logging — no prompts, no keys
def _log(stage: str, status: str, detail: str = "") -> None:
    msg = f"[LLM] stage={stage} status={status}"
    if detail:
        msg += f" detail={detail}"
    logger.info(msg)


SYSTEM_PROMPT = "You are a JSON API. Return ONLY valid JSON. No explanations, no thinking tags, no markdown, no code blocks."


def call_llm(prompt: str, system: Optional[str] = None) -> Dict[str, Any]:
    """
    Call Minimax Chat API with JSON output enforcement.

    Args:
        prompt: User prompt
        system: Optional system prompt

    Returns:
        Parsed JSON response as dict
        On failure after retries: returns {"error": "invalid_response"}
    """
    _log("call", "attempting")

    strict_prompt = (
        f"{prompt}\n\nYou must return ONLY valid JSON matching the described schema. "
        "No markdown, no explanations, no code blocks. Output valid JSON only."
    )

    result = _call_minimax_with_retry(prompt, system)
    if result is not None:
        _log("call", "success")
        return result

    # Try once with stricter prompt
    _log("call", "retry_strict")
    result = _call_minimax_with_retry(strict_prompt, system)
    if result:
        _log("call", "success")
        return result

    _log("call", "failed", "returning_safe_fallback")
    return {"error": "invalid_response"}


def _call_minimax_with_retry(prompt: str, system: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Make a single Minimax API call, parse JSON from response."""

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
    ]
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": settings.minimax_model,
        "messages": messages,
        "temperature": 0,
        "max_tokens": 4096,
    }

    for attempt in range(settings.max_retries + 1):
        try:
            response = requests.post(
                "https://api.minimax.io/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.minimax_api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=60,
            )
            response.raise_for_status()
            data = response.json()

            content = data["choices"][0]["message"]["content"]
            # Strip thinking tags before JSON parsing
            content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()
            return json.loads(content)

        except (json.JSONDecodeError, KeyError, requests.RequestException) as e:
            if attempt == settings.max_retries:
                _log("call", "error", str(e))
                return None
            continue

    return None
