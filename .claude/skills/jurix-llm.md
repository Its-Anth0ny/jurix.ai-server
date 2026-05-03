---
name: jurix-llm-integration
description: Use when working on JURIX LLM wrapper — Minimax API calls, response parsing, thinking tag stripping, retry logic, or adding new AI stages.
---

# JURIX LLM Integration

## Overview

All AI stages use `call_llm()` from `app/core/llm.py`. This is the **only** LLM integration point. Calls Minimax Chat API (`https://api.minimax.io/v1/chat/completions`) with `MiniMax-M2.7` model.

## When to Use

- Modifying LLM wrapper behavior (retry, parsing, error handling)
- Adding new AI stages that need LLM calls
- Debugging LLM API failures
- Changing model or API settings
- Understanding how JSON-only output is enforced

## call_llm Signature

```python
def call_llm(prompt: str, system: Optional[str] = None) -> Dict[str, Any]:
    """
    Returns: Parsed JSON response as dict, or {"error": "invalid_response"} on failure
    """
```

## Critical Implementation Rules

### 1. `if result is not None` — NOT `if result:`

Empty dict `{}` is a **valid** JSON response (e.g., `{"status": "approved", "issues": []}`). Using `if result:` treats `{}` as falsy and triggers unnecessary retry.

```python
# WRONG
if result:
    return result

# CORRECT
if result is not None:
    return result
```

### 2. System prompt preserved on retry

When retrying with stricter prompt, preserve the original system prompt:

```python
# WRONG — discards system prompt on retry
result = _call_minimax_with_retry(strict_prompt, None)

# CORRECT — preserves system prompt
result = _call_minimax_with_retry(strict_prompt, system)
```

### 3. Thinking tag stripping before JSON parsing

MiniMax returns `<think>...` tags wrapping JSON. Must strip before parsing:

```python
content = data["choices"][0]["message"]["content"]
content = re.sub(r'<think>.*?', '', content, flags=re.DOTALL).strip()
return json.loads(content)
```

### 4. temperature=0 for deterministic JSON-only output

```python
payload = {
    "model": settings.minimax_model,
    "messages": [...],
    "temperature": 0,  # Not 0.1 — must be exactly 0
    "max_tokens": 4096,
}
```

## LLM Service Files

| Service | File | Prompt Variable |
|---------|------|-----------------|
| Extraction | `app/services/extraction_service.py` | `FACT_EXTRACTION_PROMPT` |
| Action Plan | `app/services/action_service.py` | `ACTION_PLAN_PROMPT` |
| Audit | `app/services/audit_service.py` | `AUDIT_PROMPT` |

All use Python `.format()` — JSON literals in prompts must use `{{`/`}}`.

## Error Handling

```python
class LLMError(Exception):
    """Raised when LLM call fails after all retries."""
    pass

# In pipeline_service.py — catches LLMError from any stage
except LLMError as e:
    documents.update_one({"_id": document_id}, {"$set": {"status": "failed", "stage": current_stage, "error": str(e)}})
```