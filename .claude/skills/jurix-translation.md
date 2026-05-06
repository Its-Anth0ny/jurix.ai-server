---
name: jurix-translation
description: Use when working on the JURIX translation feature — translating extraction fields (case_details, parties, final_order, deadlines, citations) into another language via the LLM.
---

# JURIX Translation Feature

## Overview

Translates the structured extraction output for a completed document into any target language using the LLM.

```
GET extractions collection (by document_id)
  ↓
Build payload: { case_details, parties, final_order, deadlines, citations }
  ↓
translate_output(payload, language)  [LLM → returns translated JSON]
  ↓
POST /api/translate/{document_id} → TranslateResponse
```

## Key Files

| File | Role |
|------|------|
| `app/api/routes.py` | `translate_document()` endpoint — fetches extraction, calls translate_output |
| `app/services/translation_service.py` | `translate_output(output, target_lang)` — formats prompt, calls LLM, returns translated dict or original on failure |

## API Endpoint

```
POST /api/translate/{document_id}
Authorization: Bearer <jwt_token>
Content-Type: application/json

{ "language": "Hindi" }
```

**Requirements:**
- Document must exist and belong to the authenticated user
- Document must have reached `completed` status (extraction must exist in `extractions` collection)

**Response:**
```json
{
  "document_id": "...",
  "language": "Hindi",
  "translated_output": {
    "case_details": { ... },
    "parties": { ... },
    "final_order": "...",
    "deadlines": [...],
    "citations": [...]
  }
}
```

**Error cases:**
| Status | Message | Cause |
|--------|---------|-------|
| 401 | Missing/invalid authorization | No or bad Bearer token |
| 404 | Document not found | Wrong document_id or token belongs to a different user than who uploaded |
| 404 | Extraction not found | Pipeline hasn't completed yet — document status is not `completed` |

## Schemas

```python
class TranslateRequest(BaseModel):
    language: str  # free-form, e.g. "Hindi", "Marathi", "Tamil", "fr", "es"

class TranslateResponse(BaseModel):
    document_id: str
    language: str
    translated_output: dict
```

## Translation Service

`translate_output()` in `translation_service.py`:
- Serializes input dict to JSON string
- Passes to LLM with target language instruction
- Returns translated dict on success, **original dict on any failure** (silent fallback)
- Uses `call_llm()` — same LLM wrapper as all pipeline stages

```python
def translate_output(output: Dict[str, Any], target_lang: str = "en") -> Dict[str, Any]:
    ...
    result = call_llm(prompt)
    if "error" in result:
        return output   # falls back to original on LLM error
    return result
```

## Common Issues

- **"Document not found"** — token mismatch is the most common cause. The JWT must belong to the same user who uploaded the document. Run `GET /api/documents` with your token to confirm the document_id appears in the list.
- **"Extraction not found"** — document is still processing or failed. Check `GET /api/document/{id}` for `status` and `stage`.
- **Translation returns original language** — LLM silently failed; `translate_output` returns the original dict. Check LLM connectivity and `MINIMAX_API_KEY`.
