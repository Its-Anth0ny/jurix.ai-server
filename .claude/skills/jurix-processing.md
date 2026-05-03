---
name: jurix-processing-pipeline
description: Use when working on JURIX backend pipeline — PDF upload, background processing stages, extraction/action/audit LLM calls, or document status tracking.
---

# JURIX Document Processing Pipeline

## Overview

Complete pipeline: PDF upload → background processing (extraction → action plan → audit) → human review (approve/edit/reject).

```
Upload PDF → POST /api/process/{id} (background task via FastAPI BackgroundTasks)
                ↓
        run_pipeline(id)
          1. extract_text_from_pdf(id)        [pdfplumber]
          2. process_extraction(text)         [LLM → extractions collection]
          3. generate_action_plan(extraction) [LLM → actions collection]
          4. audit_action_plan(extraction, action_plan) [LLM → audits collection]
          ↓ on error: status=failed, stage=<step>
          ↓ on success: status=completed, stage=done
                ↓
        POST /api/review/{id} (human decision: approved/edited/rejected)
          → status: reviewed_approved / reviewed_rejected / reviewed_edited
```

## When to Use

- Modifying any pipeline stage (extraction, action, audit)
- Adding new fields to extraction, action_plan, or audit schemas
- Changing document status flow
- Working on the review endpoint
- Debugging processing failures

## Document Status Flow

```
uploaded → processing (extracting → generating_action → auditing → done)
         → completed → reviewed_approved / reviewed_rejected / reviewed_edited
         → failed
```

## Critical Rules

1. **Prompt brace escaping** — All prompts using `.format()` with JSON schemas:
   ```python
   FACT_EXTRACTION_PROMPT = """...{{ "case_number": "...", ... }}..."""
   ```
   Single `{` in JSON schema causes `KeyError` at runtime.

2. **ObjectId serialization** — MongoDB `find_one()` returns `_id` as `bson.objectid.ObjectId`. Pydantic can't serialize it. Use `_clean()` helper in routes.py to convert before returning JSON:
   ```python
   def _clean(doc):
       if doc is None: return {}
       result = {}
       for k, v in doc.items():
           if k == "_id": result[k] = str(v)
           elif isinstance(v, dict): result[k] = _clean(v)
           elif isinstance(v, list): result[k] = [_clean(i) if isinstance(i, dict) else i for i in v]
           else: result[k] = v
       return result
   ```

3. **Background task visibility** — `BackgroundTasks` runs in same process. No retries on failure. Client must poll `GET /api/document/{id}` to see final status.

## Review Endpoint

```python
# POST /api/review/{document_id}
# Body: {"decision": "approved"|"edited"|"rejected", "edited_output?": {...}}
# decision is ReviewDecision enum — use .value in f-strings:
status = f"reviewed_{review.decision.value}"  # produces "reviewed_approved"
```

## Quick Reference

| Stage | Service | LLM Prompt Variable |
|--------|---------|---------------------|
| Extraction | extraction_service.py | `FACT_EXTRACTION_PROMPT` |
| Action Plan | action_service.py | `ACTION_PLAN_PROMPT` |
| Audit | audit_service.py | `AUDIT_PROMPT` |

All three prompts use Python `.format()` and require doubled braces for JSON literals.