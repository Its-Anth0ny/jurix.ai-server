from datetime import datetime, timedelta, timezone
import uuid
import bcrypt
from jose import JWTError, jwt

from fastapi import APIRouter, UploadFile, File, BackgroundTasks, HTTPException, Header, Depends
from typing import Optional

from app.models.schemas import (
    UploadResponse,
    ProcessResponse,
    DocumentResponse,
    ReviewRequest,
    ReviewResponse,
    TranslateRequest,
    TranslateResponse,
    DocumentStatus,
    SignupRequest,
    LoginRequest,
    Token,
    TokenPayload,
)
from app.db.mongo import (
    get_documents,
    get_extractions,
    get_actions,
    get_audits,
    get_reviews,
    get_users,
)
from app.services.pdf_service import save_pdf, PDFValidationError
from app.services.pipeline_service import run_pipeline
from app.services.translation_service import translate_output
from app.core.config import settings


router = APIRouter()


ALGORITHM = "HS256"


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def _create_token(user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=settings.jwt_expiry_hours)
    payload = {"sub": user_id, "exp": int(expire.timestamp())}
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def _decode_token(token: str) -> Optional[str]:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        return payload.get("sub")
    except JWTError:
        return None


async def _get_current_user(authorization: str = Header(None)) -> str:
    """Extract and validate user_id from Bearer token. Raises 401 if invalid."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization header")
    token = authorization.replace("Bearer ", "")
    user_id = _decode_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return user_id


@router.post("/auth/signup", response_model=Token)
async def signup(request: SignupRequest):
    """Register a new user. Returns JWT token."""
    users = get_users()
    existing = users.find_one({"email": request.email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user_id = str(uuid.uuid4())
    password_hash = _hash_password(request.password)

    users.insert_one({
        "_id": user_id,
        "email": request.email,
        "password_hash": password_hash,
        "created_at": datetime.utcnow().isoformat(),
    })

    token = _create_token(user_id)
    return Token(token=token, user={"id": user_id, "email": request.email})


@router.post("/auth/login", response_model=Token)
async def login(request: LoginRequest):
    """Authenticate user. Returns JWT token."""
    users = get_users()
    user = users.find_one({"email": request.email})
    if not user or not _verify_password(request.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = _create_token(user["_id"])
    return Token(token=token, user={"id": user["_id"], "email": user["email"]})


@router.get("/documents")
async def list_documents(current_user: str = Depends(_get_current_user)):
    """List documents for the authenticated user."""
    docs = list(get_documents().find({"user_id": current_user}))
    return {
        "documents": [
            {
                "_id": str(doc["_id"]),
                "status": doc.get("status", "unknown"),
                "created_at": doc.get("created_at", ""),
                "stage": doc.get("stage"),
            }
            for doc in docs
        ]
    }


@router.post("/upload", response_model=UploadResponse)
async def upload_pdf(file: UploadFile = File(...), current_user: str = Depends(_get_current_user)):
    """Upload a PDF document."""
    try:
        document_id, _ = await save_pdf(file)
    except PDFValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))

    get_documents().insert_one({
        "_id": document_id,
        "file_path": f"uploads/{document_id}.pdf",
        "status": "uploaded",
        "created_at": datetime.utcnow().isoformat(),
        "user_id": current_user,
    })

    return UploadResponse(document_id=document_id)


@router.post("/process/{document_id}", response_model=ProcessResponse)
async def process_document(document_id: str, background_tasks: BackgroundTasks, current_user: str = Depends(_get_current_user)):
    """Trigger background processing pipeline."""
    doc = get_documents().find_one({"_id": document_id, "user_id": current_user})
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    background_tasks.add_task(run_pipeline, document_id)

    return ProcessResponse(document_id=document_id, status="processing")


@router.get("/document/{document_id}", response_model=DocumentResponse)
async def get_document(document_id: str, current_user: str = Depends(_get_current_user)):
    """Get document status and results."""
    doc = get_documents().find_one({"_id": document_id, "user_id": current_user})
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    response = DocumentResponse(
        document_id=document_id,
        status=DocumentStatus(doc["status"]),
        stage=doc.get("stage"),
    )

    extraction = get_extractions().find_one({"document_id": document_id})
    if extraction:
        response.extraction = {
            "case_details": extraction.get("case_details", {}),
            "parties": extraction.get("parties", {}),
            "final_order": extraction.get("final_order", ""),
            "deadlines": extraction.get("deadlines", []),
            "citations": extraction.get("citations", []),
        }

    action = get_actions().find_one({"document_id": document_id})
    if action:
        response.action_plan = {
            "decision": action.get("decision", ""),
            "actions": action.get("actions", []),
            "department": action.get("department", ""),
            "deadlines": action.get("deadlines", []),
        }

    audit = get_audits().find_one({"document_id": document_id})
    if audit:
        response.audit = {
            "status": audit.get("status", ""),
            "issues": audit.get("issues", []),
        }

    return response


@router.post("/review/{document_id}", response_model=ReviewResponse)
async def review_document(document_id: str, review: ReviewRequest, current_user: str = Depends(_get_current_user)):
    """Submit human review decision."""
    doc = get_documents().find_one({"_id": document_id, "user_id": current_user})
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if doc["status"] != "completed":
        raise HTTPException(
            status_code=400,
            detail="Document must be completed before review"
        )

    extraction = get_extractions().find_one({"document_id": document_id})
    action = get_actions().find_one({"document_id": document_id})

    if review.decision == "edited":
        final_output = review.edited_output
    else:
        def _clean(doc):
            if doc is None:
                return {}
            # Convert ObjectId to string for JSON serialization
            result = {}
            for k, v in doc.items():
                if k == "_id":
                    result[k] = str(v)
                elif isinstance(v, dict):
                    result[k] = _clean(v)
                elif isinstance(v, list):
                    result[k] = [
                        _clean(i) if isinstance(i, dict) else str(i) if hasattr(i, '__class__') and i.__class__.__name__ == 'ObjectId' else i
                        for i in v
                    ]
                else:
                    result[k] = v
            return result

        final_output = {
            "extraction": _clean(extraction) if extraction else {},
            "action_plan": _clean(action) if action else {},
        }

    get_reviews().replace_one(
        {"document_id": document_id},
        {
            "document_id": document_id,
            "final_output": final_output,
            "status": review.decision,
        },
        upsert=True,
    )

    get_documents().update_one(
        {"_id": document_id},
        {"$set": {"status": f"reviewed_{review.decision.value}"}}
    )

    return ReviewResponse(
        document_id=document_id,
        status=review.decision,
        final_output=final_output,
    )


@router.post("/translate/{document_id}", response_model=TranslateResponse)
async def translate_document(
    document_id: str,
    request: TranslateRequest,
    current_user: str = Depends(_get_current_user),
):
    """Translate extraction fields for the given document into the requested language."""
    doc = get_documents().find_one({"_id": document_id, "user_id": current_user})
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    extraction = get_extractions().find_one({"document_id": document_id})
    if not extraction:
        raise HTTPException(status_code=404, detail="Extraction not found")

    extraction_data = {
        "case_details": extraction.get("case_details", {}),
        "parties": extraction.get("parties", {}),
        "final_order": extraction.get("final_order", ""),
        "deadlines": extraction.get("deadlines", []),
        "citations": extraction.get("citations", []),
    }

    translated = translate_output(extraction_data, request.language)

    return TranslateResponse(
        document_id=document_id,
        language=request.language,
        translated_output=translated,
    )
