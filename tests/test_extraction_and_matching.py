"""Comprehensive test suite for Real Entity Extraction, Normalization, Strict Multi-Field Matching Engine, and Zero-Placeholder Verification."""

import pytest
from ai_platform.db.models import VerificationDecision
from ai_platform.services.entity_extraction_service import (
    detect_document_type,
    extract_entities_from_text,
    parse_name_components,
)
from ai_platform.services.entity_normalization_service import (
    normalize_address,
    normalize_date,
    normalize_extracted_entities,
    normalize_id_number,
    normalize_name,
)
from ai_platform.services.verification_engine import (
    calculate_jaro_winkler_similarity,
    calculate_token_sort_ratio,
    evaluate_address_match,
    evaluate_dob_match,
    evaluate_gender_match,
    evaluate_government_ids,
    evaluate_multi_field_verification,
    evaluate_name_match,
)


def test_document_type_detection():
    pan_text = "INCOME TAX DEPARTMENT PERMANENT ACCOUNT NUMBER ABCDE1234F"
    doc_type, conf = detect_document_type(pan_text)
    assert doc_type == "pan"
    assert conf > 0.90

    aadhaar_text = "GOVERNMENT OF INDIA UNIQUE IDENTIFICATION AADHAAR 1234 5678 9012"
    doc_type2, conf2 = detect_document_type(aadhaar_text)
    assert doc_type2 == "aadhaar"
    assert conf2 > 0.90


def test_pan_real_entity_extraction():
    text = """
    INCOME TAX DEPARTMENT
    GOVERNMENT OF INDIA
    PERMANENT ACCOUNT NUMBER: ABCDE1234F
    NAME: DINESH KUMAR SHARMA
    DOB: 15/04/2003
    """
    doc_type, conf, entities = extract_entities_from_text(text, "PAN_CARD")
    assert doc_type == "pan"
    assert entities["government_ids"]["pan_number"]["value"] == "ABCDE1234F"
    assert entities["identity"]["full_name"]["value"] == "DINESH KUMAR SHARMA"
    assert entities["identity"]["first_name"]["value"] == "DINESH"
    assert entities["identity"]["last_name"]["value"] == "SHARMA"
    assert entities["identity"]["date_of_birth"]["value"] == "15/04/2003"


def test_aadhaar_real_entity_extraction():
    text = """
    GOVERNMENT OF INDIA
    AADHAAR
    1234 5678 9012
    NAME: DINESH KUMAR SHARMA
    DOB: 2003-04-15
    Gender: MALE
    Address: 123 MG Road Street Bangalore Karnataka 560001
    """
    doc_type, conf, entities = extract_entities_from_text(text, "AADHAAR_CARD")
    assert doc_type == "aadhaar"
    assert entities["government_ids"]["aadhaar_number"]["value"] == "123456789012"
    assert entities["identity"]["gender"]["value"] == "Male"
    assert entities["address"]["postal_code"]["value"] == "560001"


def test_name_normalization():
    raw = "Shri Dinesh Kumar Sharma"
    clean_raw, norm = normalize_name(raw)
    assert norm == "DINESH KUMAR SHARMA"


def test_date_normalization():
    assert normalize_date("15/04/2003") == "2003-04-15"
    assert normalize_date("15-Apr-2003") == "2003-04-15"
    assert normalize_date("2003.04.15") == "2003-04-15"


def test_strict_dob_and_gender_matching():
    # Both present -> MATCH
    res_dob = evaluate_dob_match("2003-04-15", "2003-04-15")
    assert res_dob["status"] == "MATCH"
    assert res_dob["score"] == 1.0

    # One missing -> MISSING (not 100%)
    res_missing_dob = evaluate_dob_match("2003-04-15", None)
    assert res_missing_dob["status"] == "MISSING"
    assert res_missing_dob["score"] is None

    # Gender missing -> MISSING
    res_gender = evaluate_gender_match("Male", None)
    assert res_gender["status"] == "MISSING"
    assert res_gender["score"] is None


def test_multi_field_verification_engine_strict():
    primary_raw = {
        "identity": {"full_name": "Dinesh Kumar Sharma", "gender": "Male", "date_of_birth": "15/04/2003"},
        "government_ids": {"pan_number": "ABCDE1234F", "aadhaar_number": "123456789012"},
        "address": {"street": "123 MG Road", "city": "BANGALORE", "state": "KARNATAKA", "postal_code": "560001"},
    }

    supporting_raw = {
        "identity": {"full_name": "SHARMA DINESH KUMAR", "gender": "Male", "date_of_birth": "2003-04-15"},
        "government_ids": {"pan_number": "ABCDE1234F", "aadhaar_number": "123456789012"},
        "address": {"street": "123 MG Rd", "city": "BANGALORE", "state": "KARNATAKA", "postal_code": "560001"},
    }

    p_norm = normalize_extracted_entities(primary_raw)
    s_norm = normalize_extracted_entities(supporting_raw)

    decision, final_score, breakdown, report = evaluate_multi_field_verification(
        p_norm, s_norm, face_similarity_score=0.95
    )

    assert decision == VerificationDecision.VERIFIED
    assert final_score >= 85.0
    assert breakdown["identity_verification"]["dob"]["status"] == "MATCH"
    assert breakdown["face_verification"]["status"] == "MATCH"
    assert report["verdict"] == "VERIFIED"
