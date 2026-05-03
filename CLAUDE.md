# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## Project Overview

JURIX.AI — a FastAPI + Next.js pipeline that converts court judgment PDFs into structured action plans.

- **Backend**: FastAPI (Python 3.11), MongoDB Atlas, Minimax LLM
- **Frontend**: Next.js 16 (App Router), TypeScript, Tailwind CSS, shadcn/ui
- **Auth**: JWT (HS256), client-side localStorage token storage

---

## Architecture

### Backend Flow

```
Upload PDF → POST /api/process/{id} (background task via FastAPI BackgroundTasks)
                ↓
        run_pipeline(id)
          1. extract_text_from_pdf(id)       [pdfplumber]
          2. process_extraction(text)         [LLM → extraction collection]
          3. generate_action_plan(extraction) [LLM → actions collection]
          4. audit_action_plan(extraction, action_plan) [LLM → audits collection]
          ↓ on error: status=failed, stage=<step>
          ↓ on success: status=completed, stage=done
                ↓
        POST /api/review/{id} (human decision: approved/edited/rejected)
          → status: reviewed_approved / reviewed_edited / reviewed_rejected
```

All AI stages use `call_llm()` from `app/core/llm.py`. The LLM wrapper is the **only** LLM integration point.

---

## Running the Backend

```bash
# Start (python3.11 required — homebrew version, NOT system python)
# OpenSSL 3.5.1 issue may cause TLS handshake failures with MongoDB Atlas
/opt/homebrew/bin/python3.11 -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# Run tests
/opt/homebrew/bin/python3.11 -m pytest tests/

# Python version note
# python3.13 has OpenSSL 3.5.1 which is incompatible with MongoDB Atlas TLS
# python3.11 uses OpenSSL that works with Atlas
```

---

## Key Files

| File | Role |
|------|------|
| `app/core/llm.py` | Centralized LLM wrapper. `call_llm(prompt, system?)` → Minimax API, strips `<think>...` tags, returns parsed JSON dict or `{"error": "invalid_response"}`. Retry logic preserves system prompt on second attempt. |
| `app/core/config.py` | Settings via pydantic-settings. All config from env vars / `.env`. |
| `app/services/pipeline_service.py` | `run_pipeline(id)` — orchestrates extraction → action → audit. Uses `current_stage` tracking. Error handlers preserve `current_stage`. |
| `app/services/extraction_service.py` | `FACT_EXTRACTION_PROMPT` — braces **must** be doubled (`{{}}`) for Python `.format()` |
| `app/services/action_service.py` | `ACTION_PLAN_PROMPT` — same brace escaping required |
| `app/services/audit_service.py` | `AUDIT_PROMPT` — same brace escaping required |
| `app/api/routes.py` | All REST endpoints. JWT auth via `_get_current_user()` Depends. Background task runs in same process — polling required to check status. |
| `app/db/mongo.py` | MongoDB connection manager via pymongo SRV. Collections: `documents`, `extractions`, `actions`, `audits`, `reviews`, `users`. |
| `app/models/schemas.py` | Pydantic models. `DocumentStatus` includes review statuses (`reviewed_approved`, `reviewed_rejected`, `reviewed_edited`). |
| `app/services/pdf_service.py` | PDF save/get path utilities. |
| `app/services/translation_service.py` | **UNUSED** — orphaned, not integrated into pipeline. |

---

## API Endpoints

All `/api/*` routes except `/api/auth/*` require `Authorization: Bearer <jwt_token>`.

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/auth/signup` | Register → `{token, user: {id, email}}` |
| `POST` | `/api/auth/login` | Login → `{token, user: {id, email}}` |
| `GET` | `/api/documents` | List user's documents |
| `POST` | `/api/upload` | Multipart PDF upload → `{document_id}` |
| `POST` | `/api/process/{document_id}` | Trigger background pipeline → `{document_id, status: "processing"}` |
| `GET` | `/api/document/{document_id}` | Get status + extraction/action_plan/audit |
| `POST` | `/api/review/{document_id}` | Submit decision: `{decision: approved|edited|rejected, edited_output?}` |

---

## Database Collections

| Collection | Purpose |
|------------|---------|
| `documents` | PDF metadata. Key fields: `_id`, `user_id`, `file_path`, `status`, `stage`, `error` |
| `extractions` | Structured facts (case_details, parties, final_order, deadlines, citations) |
| `actions` | Generated action plan (decision, actions[], department, deadlines) |
| `audits` | Audit result (status: approved/needs_review, issues[]) |
| `reviews` | Human review decisions (final_output, status) |
| `users` | Email/password_hash, unique index on `email` |

**Document statuses:** `uploaded` → `processing` → `completed`/`failed` → `reviewed_approved`/`reviewed_rejected`/`reviewed_edited`

---

## Frontend Structure

```
app/
├── page.tsx                      # Root redirector (/ → /dashboard or /login)
├── (auth)/login/page.tsx        # Login form
├── (auth)/signup/page.tsx       # Signup form
├── (dashboard)/
│   ├── layout.tsx               # Sidebar+Topbar, route guard → /login if not authed
│   ├── dashboard/page.tsx       # Document list + upload dialog
│   └── document/[id]/page.tsx   # Document detail, tabs (extraction/action/audit), 10s polling
├── providers.tsx                # AuthProvider + ThemeProvider
└── layout.tsx                   # Root layout, Geist font, metadata
```

**Auth:** Token stored in `localStorage` under `jurix_auth` key (via `lib/auth.ts`). No HTTP-only cookies.

**API client:** `lib/api.ts` exports `api` object with all endpoints. Token passed manually per-call via `getToken()`.

---

## Critical Rules

1. **Prompt brace escaping** — All prompts using `.format()` with JSON schemas must double braces: `{{` → `{`, `}}` → `}`. This caused `KeyError` crashes in all three service prompts.

2. **Enum serialization** — `review.decision` is a `ReviewDecision` enum. Use `.value` in f-strings and response models: `f"reviewed_{review.decision.value}"` and `status=review.decision.value`. Without `.value`, produces `"reviewed_ReviewDecision.APPROVED"` which breaks `DocumentStatus` parsing.

3. **`if result is not None`** — In `llm.py`, `{}` (empty dict) is a valid JSON response. Use `if result is not None:`, NOT `if result:` which treats `{}` as falsy.

4. **ObjectId serialization** — MongoDB `find_one()` returns `_id` as `bson.objectid.ObjectId`. Pydantic cannot serialize this. The `_clean()` helper in `routes.py` converts `ObjectId` to string before returning `ReviewResponse`.

5. **`DocumentStatus` review variants** — The enum must include `REVIEWED_APPROVED`, `REVIEWED_REJECTED`, `REVIEWED_EDITED` to avoid `ValueError` when `get_document` is called on reviewed documents.

6. **Background task visibility** — `BackgroundTasks` runs in the same uvicorn process. Failures are only visible via polling `GET /api/document/{id}`. No retries, no webhooks.

---

## Configuration

Environment variables (`.env`):

```
MONGO_URI=mongodb+srv://...           # MongoDB Atlas SRV
MONGO_DB_NAME=jurix
MINIMAX_API_KEY=sk-cp-...             # Minimax API key
MINIMAX_MODEL=MiniMax-M2.7            # Model name
UPLOAD_DIR=uploads
MAX_RETRIES=1                         # LLM retry attempts
JWT_EXPIRY_HOURS=24
SECRET_KEY=...                        # Change in production
```

---

## Known Issues

- **MongoDB TLS handshake failure** — OpenSSL 3.5.1 (python3.13, system python) is incompatible with Atlas TLS. Use `python3.11` (homebrew) which has a compatible OpenSSL build.
- **`translation_service.py` is orphaned** — defined but never called in the pipeline.
- **No token refresh** — JWT expires after 24h, user must re-login manually.
- **Token in localStorage** — vulnerable to XSS. Acceptable for demo; production should use HTTP-only cookies.
- **No pagination** — `GET /api/documents` returns all user documents.
- **No PDF content validation** — `save_pdf()` only checks `.pdf` extension, not actual content/type.
- **SSL context not configurable** — pymongo TLS settings hardcoded in connection logic (python3.11 works, python3.13 fails).