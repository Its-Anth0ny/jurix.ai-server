import os
import uuid
from pathlib import Path
from typing import Tuple

from fastapi import UploadFile

from app.core.config import settings


class PDFValidationError(Exception):
    """Raised when PDF validation fails."""
    pass


async def save_pdf(file: UploadFile) -> Tuple[str, str]:
    """
    Save uploaded PDF to local storage.

    Args:
        file: Uploaded file

    Returns:
        Tuple of (document_id, file_path)

    Raises:
        PDFValidationError: If file is not a valid PDF
    """
    if not file.filename.lower().endswith(".pdf"):
        raise PDFValidationError("File must be a PDF")

    upload_path = Path(settings.upload_dir)
    upload_path.mkdir(parents=True, exist_ok=True)

    document_id = str(uuid.uuid4())
    file_path = upload_path / f"{document_id}.pdf"

    content = await file.read()
    Path(file_path).write_bytes(content)

    return document_id, str(file_path)


def get_file_path(document_id: str) -> str:
    """Get the file path for a document ID."""
    return str(Path(settings.upload_dir) / f"{document_id}.pdf")


def delete_pdf(document_id: str) -> bool:
    """Delete PDF file if it exists."""
    file_path = get_file_path(document_id)
    if os.path.exists(file_path):
        os.remove(file_path)
        return True
    return False
