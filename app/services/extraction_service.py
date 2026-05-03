import pdfplumber
from typing import Dict, Any

from app.core.llm import call_llm, LLMError
from app.services.pdf_service import get_file_path


FACT_EXTRACTION_PROMPT = """You are a legal document analyst. Extract structured facts from the provided court judgment text.

Extract ONLY facts present in the document. Do not make assumptions or interpretations.

Return ONLY valid JSON matching this schema exactly:
{{
    "case_details": {{
        "case_number": "extracted or null",
        "court": "extracted or null",
        "judge": "extracted or null",
        "case_type": "extracted or null",
        "filing_date": "extracted or null",
        "hearing_date": "extracted or null"
    }},
    "parties": {{
        "plaintiff": "extracted or null",
        "defendant": "extracted or null",
        "other_parties": [] or list of names
    }},
    "final_order": "complete text of the final order/judgment",
    "deadlines": ["deadline 1", "deadline 2"] or empty list,
    "citations": [
        {{"text": "quoted text from document", "page": N}}
    ]
}}

Return ONLY valid JSON. No explanations, no markdown, no code blocks.

Document text:
{doc_text}
"""


def extract_text_from_pdf(document_id: str) -> str:
    """
    Extract text from PDF using pdfplumber.

    Args:
        document_id: Document ID

    Returns:
        Extracted text content

    Raises:
        FileNotFoundError: If PDF doesn't exist
    """
    file_path = get_file_path(document_id)
    text_parts = []

    with pdfplumber.open(file_path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            text = page.extract_text()
            if text:
                text_parts.append(f"--- Page {page_num} ---\n{text}")

    return "\n\n".join(text_parts)


def extract_facts(text: str) -> Dict[str, Any]:
    """
    Extract structured facts from text using LLM.

    Args:
        text: Document text

    Returns:
        Structured extraction dict

    Raises:
        LLMError: If extraction fails
    """
    prompt = FACT_EXTRACTION_PROMPT.format(doc_text=text)
    return call_llm(prompt)


def process_extraction(document_id: str) -> Dict[str, Any]:
    """
    Full extraction: PDF -> text -> structured facts.

    Args:
        document_id: Document ID

    Returns:
        Extraction dict
    """
    text = extract_text_from_pdf(document_id)
    facts = extract_facts(text)
    return facts
