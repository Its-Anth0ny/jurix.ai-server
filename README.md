# JURIX.AI Backend

Court judgment PDF → structured action plan. AI-powered legal document processing pipeline.

## Overview

The backend receives court judgment PDFs, extracts structured legal facts via LLM, generates actionable compliance plans, and supports human review workflow. It exposes a REST API consumed by the frontend.

**Pipeline:** Upload → Extract → Plan → Audit → Review → Complete

## Tech Stack

| Component | Technology |
|-----------|------------|
| Framework | FastAPI (Python 3.11) |
| Database | MongoDB Atlas (SRV) |
| AI | Minimax Chat API (MiniMax-M2.7) |
| Auth | JWT (HS256), bcrypt |
| PDF Parsing | pdfplumber |

## Architecture

```
client → REST API → pipeline_service
                    ├── extraction_service (pdfplumber → LLM → extraction)
                    ├── action_service (LLM → action_plan)
                    └── audit_service (LLM → audit)
                         ↓
                    MongoDB collections
```

All AI stages are centralized in `app/core/llm.py` — the **only** LLM integration point.

## Core Features

### Authentication
- JWT-based signup/login
- Bearer token required for protected routes
- Passwords hashed with bcrypt

### Document Processing
- PDF upload to local storage
- Background pipeline triggered via FastAPI `BackgroundTasks`
- Stage tracking: `extracting → generating_action → auditing → done`
- Polling required to check background task status

### AI Pipeline
1. **Extraction** — pdfplumber extracts text → LLM extracts case details, parties, deadlines, citations
2. **Action Plan** — LLM generates compliance/appeal decision with action items and deadlines
3. **Audit** — LLM validates action plan against extraction for hallucinations/inconsistencies

### Review System
Human decision on completed documents:
- `approved` — accept AI-generated plan
- `rejected` — discard, mark as reviewed
- `edited` — override with custom extraction/action_plan

## API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/api/auth/signup` | — | Register → `{token, user}` |
| `POST` | `/api/auth/login` | — | Login → `{token, user}` |
| `GET` | `/api/documents` | Bearer | List user's documents |
| `POST` | `/api/upload` | Bearer | Upload PDF → `{document_id}` |
| `POST` | `/api/process/{id}` | Bearer | Trigger background pipeline |
| `GET` | `/api/document/{id}` | Bearer | Get document + extraction/action_plan/audit |
| `POST` | `/api/review/{id}` | Bearer | Submit approve/edit/reject decision |

## Database Collections

| Collection | Purpose |
|------------|---------|
| `users` | email, password_hash |
| `documents` | PDF metadata, status, stage, user_id |
| `extractions` | case_details, parties, final_order, deadlines, citations |
| `actions` | decision, actions[], department, deadlines |
| `audits` | status (approved/needs_review), issues[] |
| `reviews` | final_output, decision status |

## Setup

### Requirements
- Python 3.11 (homebrew, **not** system Python — 3.13 has TLS incompatibility with MongoDB Atlas)
- MongoDB Atlas cluster (SRV connection)

### Installation

```bash
pip install -r requirements.txt
```

### Environment Variables

Create `.env` from `.env.example`:

```env
MONGO_URI=mongodb+srv://<user>:<pass>@cluster0.kh89v9t.mongodb.net/?appName=Cluster0&authSource=admin
MONGO_DB_NAME=jurix
MINIMAX_API_KEY=sk-cp-...
MINIMAX_MODEL=MiniMax-M2.7
UPLOAD_DIR=uploads
MAX_RETRIES=1
SECRET_KEY=<your-secret-key>
JWT_EXPIRY_HOURS=24
```

### Run

```bash
/opt/homebrew/bin/python3.11 -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Test

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/
```

## Integration with Frontend

Frontend communicates at `http://localhost:8000` (configurable via `NEXT_PUBLIC_API_URL`):

```typescript
// Token passed per-request
const token = getToken() // from localStorage
await api.getDocument(id, token)
await api.reviewDocument(id, 'approved', undefined, token)
```

## Project Structure

```
app/
├── main.py              # FastAPI app, CORS, lifespan
├── api/routes.py        # All endpoints + auth helpers
├── core/
│   ├── config.py        # pydantic-settings from .env
│   └── llm.py           # Minimax wrapper, JSON parsing, retry
├── db/mongo.py          # MongoDB connection manager
├── models/schemas.py     # Pydantic request/response models
└── services/
    ├── pipeline_service.py    # run_pipeline orchestrator
    ├── extraction_service.py  # PDF → text → facts
    ├── action_service.py      # facts → action plan
    ├── audit_service.py       # cross-check validation
    └── pdf_service.py         # file save/get utilities
```
