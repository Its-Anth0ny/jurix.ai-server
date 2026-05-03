import pytest
from app.core.config import settings
from app.services.pdf_service import get_file_path, PDFValidationError
from app.services.translation_service import translate_output


def test_settings_loaded():
    """Verify settings can be loaded."""
    assert settings.mongo_db_name == "jurix"


def test_get_file_path():
    """Test file path generation."""
    path = get_file_path("test-123")
    assert "test-123" in path
    assert path.endswith(".pdf")


def test_translation_service_stub():
    """Test translation stub returns input."""
    input_data = {"key": "value", "nested": {"a": 1}}
    result = translate_output(input_data)
    assert result == input_data


def test_pdf_validation_error_exists():
    """Test PDFValidationError exception exists."""
    assert PDFValidationError is not None
