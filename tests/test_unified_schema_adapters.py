from ai_platform.schema.legacy_adapters import (
    adapt_face_detection_result,
    adapt_face_verification_result,
    adapt_legacy_identity_document,
    adapt_unified_to_feature_user,
)
from ai_platform.schema.unified_schema import UnifiedDocumentType


def test_adapt_nested_aadhaar_payload():
    payload = {
        "filename": "aadhaar.jpg",
        "doc_type": "Aadhaar Card",
        "unique_id": "123412341234",
        "raw_text": "sample",
        "extracted_data": {
            "front_data": {
                "full_name_en": "Anita Rao",
                "date_of_birth": "01-02-1990",
                "gender": "FEMALE",
                "aadhaar_number": "123412341234",
            },
            "back_data": {"address": "Bengaluru", "pincode": "560001"},
            "validation_status": "success",
        },
    }

    unified = adapt_legacy_identity_document(payload)

    assert unified.document_type == UnifiedDocumentType.AADHAAR_CARD
    assert unified.extracted_data["full_name_en"] == "Anita Rao"
    assert unified.extracted_data["aadhaar_number"] == "123412341234"
    assert unified.extracted_data["address"] == "Bengaluru"


def test_adapt_pan_to_feature_user():
    unified = adapt_legacy_identity_document(
        {
            "document_type": "PAN Card",
            "extracted_data": {
                "full_name_en": "Rahul Mehta",
                "pan_number": "ABCDE1234F",
            },
        }
    )

    user = adapt_unified_to_feature_user(unified)

    assert user.user_name == "Rahul Mehta"
    assert user.is_pan_verified is True
    assert user.pan_number == "ABCDE1234F"
    assert user.is_aadhaar_verified is False


def test_adapt_face_detection_and_verification():
    face = adapt_face_detection_result(
        {"face_id": "f1", "page": 2, "coords": [10, 20, 50, 80], "confidence": 0.91},
        document_id=7,
        bbox_format="xyxy",
    )
    verified = adapt_face_verification_result(face, {"same_person": True, "probability": 0.87})

    assert face.bbox_left == 10
    assert face.bbox_width == 40
    assert verified.verification_result == "match"
    assert verified.verification_confidence == 0.87
