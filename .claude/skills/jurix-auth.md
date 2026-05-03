---
name: jurix-auth-backend
description: Use when working on JURIX backend authentication — JWT signup/login, token verification, protected route dependencies, or password hashing.
---

# JURIX Backend Auth

## Overview

JWT-based auth (HS256, 24h expiry). Backend signup/login return `{token, user: {id, email}}`. All `/api/*` routes except `/api/auth/*` require `Authorization: Bearer <token>` via `_get_current_user()` dependency.

## When to Use

- Modifying auth endpoints (signup, login)
- Adding new protected routes
- Changing JWT payload structure or expiry
- Changing password hashing or verification
- Debugging 401 errors on protected routes

## Auth Implementation

```python
# routes.py
ALGORITHM = "HS256"

def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def _verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())

def _create_token(user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=settings.jwt_expiry_hours)
    payload = {"sub": user_id, "exp": int(expire.timestamp())}
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)

async def _get_current_user(authorization: str = Header(None)) -> str:
    # Raises HTTPException 401 if missing/invalid
    token = authorization.replace("Bearer ", "")
    user_id = _decode_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return user_id
```

## ReviewDecision Enum Rule

When updating document status after review, use `.value`:

```python
# WRONG — gives "reviewed_ReviewDecision.APPROVED"
status = f"reviewed_{review.decision}"

# CORRECT — gives "reviewed_approved"
status = f"reviewed_{review.decision.value}"
```

## DocumentStatus Review Variants

Must include all three review statuses in `DocumentStatus` enum:

```python
class DocumentStatus(str, Enum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    REVIEWED_APPROVED = "reviewed_approved"
    REVIEWED_REJECTED = "reviewed_rejected"
    REVIEWED_EDITED = "reviewed_edited"
```

Missing variants cause `ValueError` when `get_document` is called on reviewed documents.

## Quick Reference

| Endpoint | Auth | Request | Response |
|----------|------|---------|----------|
| `POST /api/auth/signup` | None | `{email, password}` | `{token, user: {id, email}}` |
| `POST /api/auth/login` | None | `{email, password}` | `{token, user: {id, email}}` |
| `GET /api/documents` | Bearer | — | `{documents: [...]}` |
| `POST /api/upload` | Bearer | multipart PDF | `{document_id}` |
| `POST /api/process/{id}` | Bearer | — | `{document_id, status: "processing"}` |
| `GET /api/document/{id}` | Bearer | — | full document with AI outputs |
| `POST /api/review/{id}` | Bearer | `{decision, edited_output?}` | `{document_id, status, final_output}` |