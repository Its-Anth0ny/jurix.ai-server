from pydantic import BaseModel, Field
from typing import Optional, List, Any
from datetime import datetime
from enum import Enum


class DocumentStatus(str, Enum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    REVIEWED_APPROVED = "reviewed_approved"
    REVIEWED_REJECTED = "reviewed_rejected"
    REVIEWED_EDITED = "reviewed_edited"


class ReviewDecision(str, Enum):
    APPROVED = "approved"
    EDITED = "edited"
    REJECTED = "rejected"


class AuditStatus(str, Enum):
    APPROVED = "approved"
    NEEDS_REVIEW = "needs_review"


class DecisionType(str, Enum):
    COMPLY = "comply"
    APPEAL = "appeal"


# Auth schemas
class SignupRequest(BaseModel):
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


class UserInDB(BaseModel):
    id: str
    email: str
    password_hash: str
    created_at: str


class Token(BaseModel):
    token: str
    user: dict  # {"id": str, "email": str}


class TokenPayload(BaseModel):
    sub: str  # user_id
    exp: int


class Citation(BaseModel):
    text: str
    page: int


class CaseDetails(BaseModel):
    case_number: Optional[str] = None
    court: Optional[str] = None
    judge: Optional[str] = None
    case_type: Optional[str] = None
    filing_date: Optional[str] = None
    hearing_date: Optional[str] = None


class Parties(BaseModel):
    plaintiff: Optional[str] = None
    defendant: Optional[str] = None
    other_parties: Optional[List[str]] = None


class Extraction(BaseModel):
    case_details: CaseDetails = Field(default_factory=CaseDetails)
    parties: Parties = Field(default_factory=Parties)
    final_order: str = ""
    deadlines: List[str] = Field(default_factory=list)
    citations: List[Citation] = Field(default_factory=list)


class ActionItem(BaseModel):
    action: str
    deadline: Optional[str] = None
    responsible_party: Optional[str] = None


class ActionPlan(BaseModel):
    decision: DecisionType
    actions: List[ActionItem] = Field(default_factory=list)
    department: str = ""
    deadlines: List[str] = Field(default_factory=list)


class AuditResult(BaseModel):
    status: AuditStatus
    issues: List[str] = Field(default_factory=list)


class ReviewOutput(BaseModel):
    final_output: dict
    status: str


class DocumentResponse(BaseModel):
    document_id: str
    status: DocumentStatus
    stage: Optional[str] = None
    extraction: Optional[dict] = None
    action_plan: Optional[dict] = None
    audit: Optional[dict] = None


class UploadResponse(BaseModel):
    document_id: str


class ProcessResponse(BaseModel):
    document_id: str
    status: str = "processing"


class ReviewRequest(BaseModel):
    decision: ReviewDecision
    edited_output: Optional[dict] = None


class ReviewResponse(BaseModel):
    document_id: str
    status: str
    final_output: Optional[dict] = None


class TranslateRequest(BaseModel):
    language: str  # e.g. "Hindi", "Marathi", "Tamil", "fr", "es"


class TranslateResponse(BaseModel):
    document_id: str
    language: str
    translated_output: dict
