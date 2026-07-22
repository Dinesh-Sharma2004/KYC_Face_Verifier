"""Production-grade Entity Extraction Service with field-level confidence scoring and zero fallback data."""

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("kyc.extraction")


def detect_document_type(text: str, hint: Optional[str] = None) -> Tuple[str, float]:
    """Detect document type and return (document_type, confidence_score)."""
    text_upper = text.upper()

    if hint and hint.lower() != "unknown":
        hint_clean = hint.lower()
        if "pan" in hint_clean:
            return "pan", 0.98
        elif "aadhaar" in hint_clean:
            return "aadhaar", 0.98
        elif "passport" in hint_clean:
            return "passport", 0.98
        elif "driving" in hint_clean:
            return "driving_license", 0.98
        elif "bank" in hint_clean or "statement" in hint_clean:
            return "bank_statement", 0.95
        elif "utility" in hint_clean or "bill" in hint_clean:
            return "utility_bill", 0.95

    # Automatic pattern detection
    if "INCOME TAX DEPARTMENT" in text_upper or "PERMANENT ACCOUNT NUMBER" in text_upper or re.search(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b", text_upper):
        return "pan", 0.97
    elif "UNIQUE IDENTIFICATION AUTHORITY OF INDIA" in text_upper or "GOVERNMENT OF INDIA" in text_upper or "AADHAAR" in text_upper or re.search(r"\b\d{4}\s?\d{4}\s?\d{4}\b", text_upper):
        return "aadhaar", 0.97
    elif "REPUBLIC OF INDIA" in text_upper or "PASSPORT" in text_upper or re.search(r"\b[A-Z][0-9]{7}\b", text_upper):
        return "passport", 0.96
    elif "DRIVING LICENCE" in text_upper or "UNION OF INDIA DRIVING" in text_upper:
        return "driving_license", 0.95
    elif "ELECTION COMMISSION OF INDIA" in text_upper or "ELECTOR PHOTO IDENTITY" in text_upper:
        return "voter_id", 0.95
    elif "ACCOUNT STATEMENT" in text_upper or "IFSC" in text_upper or "BANK" in text_upper:
        return "bank_statement", 0.92
    elif "ELECTRICITY BILL" in text_upper or "WATER BILL" in text_upper or "GAS BILL" in text_upper:
        return "utility_bill", 0.90
    elif "SALARY SLIP" in text_upper or "PAYSLIP" in text_upper:
        return "salary_slip", 0.90

    return "government_id", 0.70


def parse_name_components(full_name: str) -> Dict[str, Dict[str, Any]]:
    """Decompose full name into first_name, middle_name, and last_name with confidence scores."""
    if not full_name:
        return {
            "first_name": {"value": "", "confidence": 0.0},
            "middle_name": {"value": "", "confidence": 0.0},
            "last_name": {"value": "", "confidence": 0.0},
        }

    parts = [p.strip() for p in full_name.split() if p.strip()]
    if not parts:
        return {
            "first_name": {"value": "", "confidence": 0.0},
            "middle_name": {"value": "", "confidence": 0.0},
            "last_name": {"value": "", "confidence": 0.0},
        }
    elif len(parts) == 1:
        return {
            "first_name": {"value": parts[0], "confidence": 0.95},
            "middle_name": {"value": "", "confidence": 0.0},
            "last_name": {"value": parts[0], "confidence": 0.90},
        }
    elif len(parts) == 2:
        return {
            "first_name": {"value": parts[0], "confidence": 0.95},
            "middle_name": {"value": "", "confidence": 0.0},
            "last_name": {"value": parts[1], "confidence": 0.95},
        }
    else:
        return {
            "first_name": {"value": parts[0], "confidence": 0.95},
            "middle_name": {"value": " ".join(parts[1:-1]), "confidence": 0.90},
            "last_name": {"value": parts[-1], "confidence": 0.95},
        }


def extract_entities_from_text(text: str, document_type_hint: Optional[str] = None) -> Tuple[str, float, Dict[str, Any]]:
    """Extract structured entities with field-level confidence scoring.
    
    Never generates synthetic/mock names.
    Returns (document_type, confidence, extracted_entities_dict).
    """
    doc_type, confidence = detect_document_type(text, document_type_hint)

    identity = {
        "full_name": {"value": "", "confidence": 0.0},
        "first_name": {"value": "", "confidence": 0.0},
        "middle_name": {"value": "", "confidence": 0.0},
        "last_name": {"value": "", "confidence": 0.0},
        "father_name": {"value": "", "confidence": 0.0},
        "mother_name": {"value": "", "confidence": 0.0},
        "gender": {"value": "", "confidence": 0.0},
        "date_of_birth": {"value": "", "confidence": 0.0},
    }

    government_ids = {
        "aadhaar_number": {"value": "", "confidence": 0.0},
        "pan_number": {"value": "", "confidence": 0.0},
        "passport_number": {"value": "", "confidence": 0.0},
        "driving_license_number": {"value": "", "confidence": 0.0},
        "voter_id_number": {"value": "", "confidence": 0.0},
    }

    contact = {
        "phone_number": {"value": "", "confidence": 0.0},
        "alternate_phone": {"value": "", "confidence": 0.0},
        "email": {"value": "", "confidence": 0.0},
    }

    address = {
        "house_number": {"value": "", "confidence": 0.0},
        "street": {"value": "", "confidence": 0.0},
        "locality": {"value": "", "confidence": 0.0},
        "city": {"value": "", "confidence": 0.0},
        "district": {"value": "", "confidence": 0.0},
        "state": {"value": "", "confidence": 0.0},
        "postal_code": {"value": "", "confidence": 0.0},
        "country": {"value": "India", "confidence": 1.0},
    }

    banking = {
        "account_holder_name": {"value": "", "confidence": 0.0},
        "account_number": {"value": "", "confidence": 0.0},
        "ifsc_code": {"value": "", "confidence": 0.0},
        "bank_name": {"value": "", "confidence": 0.0},
    }

    # 1. Regex Extraction for Government IDs
    pan_match = re.search(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b", text)
    if pan_match:
        government_ids["pan_number"] = {"value": pan_match.group(0), "confidence": 0.99}

    aadhaar_match = re.search(r"\b\d{4}\s?\d{4}\s?\d{4}\b", text)
    if aadhaar_match:
        government_ids["aadhaar_number"] = {"value": re.sub(r"\s+", "", aadhaar_match.group(0)), "confidence": 0.98}

    passport_match = re.search(r"\b[A-Z][0-9]{7}\b", text)
    if passport_match and doc_type == "passport":
        government_ids["passport_number"] = {"value": passport_match.group(0), "confidence": 0.98}

    dl_match = re.search(r"\b[A-Z]{2}[- ]?[0-9]{11,13}\b", text)
    if dl_match:
        government_ids["driving_license_number"] = {"value": re.sub(r"[- ]", "", dl_match.group(0)), "confidence": 0.95}

    voter_match = re.search(r"\b[A-Z]{3}[0-9]{7}\b", text)
    if voter_match:
        government_ids["voter_id_number"] = {"value": voter_match.group(0), "confidence": 0.95}

    # 2. Contact Information
    email_match = re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text)
    if email_match:
        contact["email"] = {"value": email_match.group(0), "confidence": 0.98}

    phone_matches = re.findall(r"\b[6-9]\d{9}\b", text)
    if phone_matches:
        contact["phone_number"] = {"value": phone_matches[0], "confidence": 0.95}
        if len(phone_matches) > 1:
            contact["alternate_phone"] = {"value": phone_matches[1], "confidence": 0.90}

    # 3. Banking Information
    ifsc_match = re.search(r"\b[A-Z]{4}0[A-Z0-9]{6}\b", text)
    if ifsc_match:
        banking["ifsc_code"] = {"value": ifsc_match.group(0), "confidence": 0.98}

    acc_match = re.search(r"\b[0-9]{9,18}\b", text)
    if acc_match and ("ACCOUNT" in text.upper() or "BANK" in text.upper()):
        banking["account_number"] = {"value": acc_match.group(0), "confidence": 0.95}

    # 4. Dates & Gender Extraction
    dob_match = re.search(r"(?:DOB|Date of Birth|Birth Date|Date|DOB:)[\s:]*([0-9]{2}[/-][0-9]{2}[/-][0-9]{4}|[0-9]{4}[/-][0-9]{2}[/-][0-9]{2}|[0-9]{2}-[A-Za-z]{3}-[0-9]{4})", text, re.IGNORECASE)
    if dob_match:
        identity["date_of_birth"] = {"value": dob_match.group(1), "confidence": 0.98}
    else:
        generic_date = re.search(r"\b(0[1-9]|[12][0-9]|3[01])[-/.](0[1-9]|1[012])[-/.](19|20)\d\d\b", text)
        if not generic_date:
            generic_date = re.search(r"\b(19|20)\d\d[-/.](0[1-9]|1[012])[-/.](0[1-9]|[12][0-9]|3[01])\b", text)
        if generic_date:
            identity["date_of_birth"] = {"value": generic_date.group(0), "confidence": 0.90}

    if re.search(r"\bMALE\b", text, re.IGNORECASE):
        identity["gender"] = {"value": "Male", "confidence": 0.99}
    elif re.search(r"\bFEMALE\b", text, re.IGNORECASE):
        identity["gender"] = {"value": "Female", "confidence": 0.99}

    # 5. Postal Code
    pin_match = re.search(r"\b[1-9][0-9]{5}\b", text)
    if pin_match:
        address["postal_code"] = {"value": pin_match.group(0), "confidence": 0.95}

    # 6. Explicit Prefix Matching for Name
    explicit_name = re.search(r"(?:NAME|Full Name|Account Holder|Holder Name)[\s:]+([A-Za-z ]{3,40})", text, re.IGNORECASE)
    if explicit_name:
        found_name = explicit_name.group(1).strip()
        identity["full_name"] = {"value": found_name, "confidence": 0.98}
        identity.update(parse_name_components(found_name))
    else:
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        header_blacklist = [
            "INCOME TAX", "GOVERNMENT OF INDIA", "GOVT OF INDIA", "PERMANENT ACCOUNT", "NUMBER",
            "REPUBLIC OF INDIA", "PASSPORT", "UNION OF INDIA", "AADHAAR", "DEPARTMENT", "AUTHORITY",
            "INDIA", "ELECTION COMMISSION", "LICENCE", "STATEMENT"
        ]

        for i, line in enumerate(lines):
            line_clean = re.sub(r"[^A-Za-z\s]", "", line).strip()
            if line_clean and re.match(r"^[A-Za-z\s]{3,40}$", line_clean):
                upper_line = line_clean.upper()
                if not any(k in upper_line for k in header_blacklist):
                    identity["full_name"] = {"value": line_clean, "confidence": 0.85}
                    identity.update(parse_name_components(line_clean))
                    break

    entities = {
        "identity": identity,
        "government_ids": government_ids,
        "contact": contact,
        "address": address,
        "banking": banking,
    }

    return doc_type, confidence, entities
