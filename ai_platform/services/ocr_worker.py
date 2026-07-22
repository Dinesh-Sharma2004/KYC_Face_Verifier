"""OCR Worker service for extracting raw text from uploaded KYC documents with logging and quality validation."""

import logging
import re
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger("kyc.ocr")
logger.setLevel(logging.INFO)
if not logger.handlers:
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter("[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s"))
    logger.addHandler(ch)

REJECTED_PLACEHOLDERS = [
    "sample fallback document content",
    "sample text extracted",
    "dummy document",
    "unknown user",
    "test data",
    "sample user",
]


def validate_ocr_quality(raw_text: str) -> Tuple[bool, str]:
    """Validate raw OCR text against minimum length and placeholder rejection rules."""
    if not raw_text or not raw_text.strip():
        return False, "EMPTY_OCR_TEXT"

    text_clean = raw_text.strip()
    if len(text_clean) < 20:
        return False, "INSUFFICIENT_TEXT_LENGTH"

    text_lower = text_clean.lower()
    for placeholder in REJECTED_PLACEHOLDERS:
        if placeholder in text_lower and len(text_clean) < 100:
            return False, f"REJECTED_PLACEHOLDER_DETECTED: {placeholder}"

    return True, "OK"


def process_ocr_document(
    document_bytes: bytes,
    filename: str,
    document_type_hint: Optional[str] = None
) -> Tuple[str, str, float, str]:
    """Perform actual OCR extraction on raw document bytes.
    
    Returns (status, raw_text, ocr_confidence, error_message).
    """
    raw_text = ""
    try:
        from PIL import Image
        import io
        import pytesseract

        img = Image.open(io.BytesIO(document_bytes))
        raw_text = pytesseract.image_to_string(img)
    except Exception as e:
        logger.warning("Pytesseract extraction unvailable for %s: %s", filename, str(e))
        try:
            raw_text = document_bytes.decode("utf-8", errors="ignore")
        except Exception:
            raw_text = ""

    # Log actual OCR output for auditability
    logger.info("OCR OUTPUT for document: %s", filename)
    logger.info("OCR extraction completed with %s characters of text.", len(raw_text))

    is_valid, quality_msg = validate_ocr_quality(raw_text)
    if not is_valid:
        logger.error("OCR Quality check failed for %s: %s", filename, quality_msg)
        return "OCR_FAILED", raw_text, 0.0, quality_msg

    # Calculate confidence based on text length and character ratio
    alpha_chars = sum(1 for c in raw_text if c.isalnum())
    confidence = round(min(1.0, alpha_chars / (len(raw_text) + 1) + 0.3), 2)
    return "COMPLETED", raw_text, confidence, ""
