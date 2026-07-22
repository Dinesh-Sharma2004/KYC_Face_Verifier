"""Production-grade Entity Normalization Service for standardizing names, dates, addresses, and IDs."""

import re
from typing import Any, Dict, Optional, Tuple
from dateutil import parser


def extract_val(field: Any) -> str:
    """Helper to extract string value whether field is dict {"value": "..."} or raw string."""
    if isinstance(field, dict):
        return str(field.get("value") or "").strip()
    return str(field or "").strip()


def normalize_name(raw_name: Optional[str]) -> Tuple[str, str]:
    """Normalize full name string into (raw_name, normalized_name).
    
    Strips titles (Mr, Ms, Mrs, Dr, Shri, Smt), punctuation, OCR artifacts, and extra whitespace.
    """
    val = extract_val(raw_name)
    if not val:
        return "", ""

    # Remove common honorific titles
    clean_no_title = re.sub(r"^(MR|MS|MRS|DR|SHRI|SMT|KUMAR)\.?\s+", "", val, flags=re.IGNORECASE)
    # Remove special punctuation
    clean_alpha = re.sub(r"[^A-Za-z\s]", "", clean_no_title)
    # Normalize whitespace and uppercase
    normalized = " ".join(clean_alpha.upper().split())
    return val, normalized


def normalize_date(raw_date: Optional[str]) -> Optional[str]:
    """Normalize date string into canonical YYYY-MM-DD format using dateutil parser."""
    val = extract_val(raw_date)
    if not val:
        return None

    try:
        dt = parser.parse(val, dayfirst=True)
        return dt.strftime("%Y-%m-%d")
    except Exception:
        m = re.search(r"(\d{4})[-/.](\d{2})[-/.](\d{2})", val)
        if m:
            return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
        m2 = re.search(r"(\d{2})[-/.](\d{2})[-/.](\d{4})", val)
        if m2:
            return f"{m2.group(3)}-{m2.group(2)}-{m2.group(1)}"
        return val


def normalize_address(raw_address: Optional[str]) -> str:
    """Normalize street address standardizing Road -> Rd, Street -> St, Apartment -> Apt, Avenue -> Ave."""
    val = extract_val(raw_address)
    if not val:
        return ""

    text = val.upper()
    replacements = {
        r"\bROAD\b": "RD",
        r"\bSTREET\b": "ST",
        r"\bAPARTMENT\b": "APT",
        r"\bAVENUE\b": "AVE",
        r"\bBUILDING\b": "BLDG",
        r"\bFLOOR\b": "FL",
        r"\bLANE\b": "LN",
        r"\bCROSS\b": "CRS",
        r"\bMAIN\b": "MN",
    }

    for pattern, repl in replacements.items():
        text = re.sub(pattern, repl, text)

    clean = re.sub(r"[^\w\s]", " ", text)
    return " ".join(clean.split())


def normalize_id_number(raw_id: Optional[str]) -> str:
    """Normalize government or bank ID numbers by stripping non-alphanumeric chars and uppercasing."""
    val = extract_val(raw_id)
    if not val:
        return ""
    return re.sub(r"[^A-Za-z0-9]", "", val).upper()


def normalize_extracted_entities(raw_entities: Dict[str, Any]) -> Dict[str, Any]:
    """Perform comprehensive entity normalization over extracted entity dictionary."""
    normalized = {}

    # 1. Identity Normalization
    identity = raw_entities.get("identity", {})
    raw_full_name = extract_val(identity.get("full_name"))
    raw_name, norm_name = normalize_name(raw_full_name)

    normalized["identity"] = {
        "raw_name": raw_name,
        "normalized_name": norm_name,
        "first_name": extract_val(identity.get("first_name")).upper(),
        "middle_name": extract_val(identity.get("middle_name")).upper(),
        "last_name": extract_val(identity.get("last_name")).upper(),
        "father_name": normalize_name(extract_val(identity.get("father_name")))[1],
        "gender": extract_val(identity.get("gender")).capitalize(),
        "normalized_dob": normalize_date(extract_val(identity.get("date_of_birth"))),
        "raw_dob": extract_val(identity.get("date_of_birth")),
    }

    # 2. Government IDs Normalization
    gov_ids = raw_entities.get("government_ids", {})
    normalized["government_ids"] = {
        "aadhaar_number": normalize_id_number(gov_ids.get("aadhaar_number")),
        "pan_number": normalize_id_number(gov_ids.get("pan_number")),
        "passport_number": normalize_id_number(gov_ids.get("passport_number")),
        "driving_license_number": normalize_id_number(gov_ids.get("driving_license_number")),
        "voter_id_number": normalize_id_number(gov_ids.get("voter_id_number")),
    }

    # 3. Address Normalization
    addr = raw_entities.get("address", {})
    raw_street = extract_val(addr.get("street"))
    normalized["address"] = {
        "raw_address": raw_street,
        "normalized_street": normalize_address(raw_street),
        "city": extract_val(addr.get("city")).upper(),
        "state": extract_val(addr.get("state")).upper(),
        "postal_code": normalize_id_number(addr.get("postal_code")),
        "country": (extract_val(addr.get("country")) or "INDIA").upper(),
    }

    # 4. Contact & Banking Normalization
    contact = raw_entities.get("contact", {})
    normalized["contact"] = {
        "phone_number": normalize_id_number(contact.get("phone_number")),
        "email": extract_val(contact.get("email")).lower(),
    }

    banking = raw_entities.get("banking", {})
    normalized["banking"] = {
        "account_holder_name": normalize_name(extract_val(banking.get("account_holder_name")))[1],
        "account_number": normalize_id_number(banking.get("account_number")),
        "ifsc_code": normalize_id_number(banking.get("ifsc_code")),
    }

    return normalized
