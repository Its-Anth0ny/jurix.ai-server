from datetime import datetime

from app.db.mongo import (
    get_documents,
    get_extractions,
    get_actions,
    get_audits,
)
from app.services.extraction_service import process_extraction
from app.services.action_service import generate_action_plan
from app.services.audit_service import audit_action_plan
from app.core.llm import LLMError


def run_pipeline(document_id: str) -> None:
    """
    Run full extraction -> action -> audit pipeline.

    Updates document status and stage throughout. Marks as failed on any error.

    Args:
        document_id: Document ID to process
    """
    documents = get_documents()
    current_stage = "extracting"

    documents.update_one(
        {"_id": document_id},
        {"$set": {"status": "processing", "stage": current_stage}}
    )

    try:
        extraction = process_extraction(document_id)
        current_stage = "generating_action"

        documents.update_one(
            {"_id": document_id},
            {"$set": {"stage": current_stage}}
        )

        get_extractions().replace_one(
            {"document_id": document_id},
            {"document_id": document_id, **extraction},
            upsert=True,
        )

        action_plan = generate_action_plan(extraction)
        current_stage = "auditing"

        documents.update_one(
            {"_id": document_id},
            {"$set": {"stage": current_stage}}
        )

        get_actions().replace_one(
            {"document_id": document_id},
            {"document_id": document_id, **action_plan},
            upsert=True,
        )

        audit_result = audit_action_plan(extraction, action_plan)

        get_audits().replace_one(
            {"document_id": document_id},
            {"document_id": document_id, **audit_result},
            upsert=True,
        )

        documents.update_one(
            {"_id": document_id},
            {"$set": {"status": "completed", "stage": "done"}}
        )

    except LLMError as e:
        documents.update_one(
            {"_id": document_id},
            {"$set": {"status": "failed", "stage": current_stage, "error": str(e)}}
        )
    except Exception as e:
        documents.update_one(
            {"_id": document_id},
            {"$set": {"status": "failed", "stage": current_stage, "error": str(e)}}
        )