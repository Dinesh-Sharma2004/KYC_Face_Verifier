"""Adapters from discovered legacy schemas to unified contracts."""

from datetime import date, datetime
from typing import Any, Dict, Mapping, Optional

from .unified_schema import (
    DocumentExtractionRecord,
    FaceRecordContract,
    FeatureEngineeringUserRecord,
    IdentityDocumentData,
    UnifiedDocumentType,
)


LEGACY_DOCUMENT_TYPE_MAP = {
    "aadhaar": UnifiedDocumentType.AADHAAR_CARD,
    "aadhar": UnifiedDocumentType.AADHAAR_CARD,
    "aadhaar card": UnifiedDocumentType.AADHAAR_CARD,
    "aadhar card": UnifiedDocumentType.AADHAAR_CARD,
    "AADHAAR_CARD": UnifiedDocumentType.AADHAAR_CARD,
    "PAN Card": UnifiedDocumentType.PAN_CARD,
    "pan": UnifiedDocumentType.PAN_CARD,
    "pan card": UnifiedDocumentType.PAN_CARD,
    "PAN_CARD": UnifiedDocumentType.PAN_CARD,
}


def normalize_document_type(value: Any) -> UnifiedDocumentType:
    if isinstance(value, UnifiedDocumentType):
        return value
    text = str(value or "UNKNOWN").strip()
    if text in UnifiedDocumentType.__members__:
        return UnifiedDocumentType[text]
    return LEGACY_DOCUMENT_TYPE_MAP.get(text, LEGACY_DOCUMENT_TYPE_MAP.get(text.lower(), UnifiedDocumentType.UNKNOWN))


def _first_present(*values: Any) -> Any:
    for value in values:
        if value not in (None, ""):
            return value
    return None


def _coerce_date(value: Any) -> Optional[date | str]:
    if value in (None, ""):
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, datetime):
        return value.date()
    text = str(value)
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%d.%m.%Y"):
        try:
            return datetime.strptime(text.split(" ")[0], fmt).date()
        except ValueError:
            continue
    return text


def adapt_legacy_identity_document(payload: Mapping[str, Any]) -> DocumentExtractionRecord:
    """Adapt outputs from legacy PAN/Aadhaar extractors.

    Supports:
    - `agents/utils/schemas.py` flat fields
    - Flask KYC nested `front_data` / `back_data`
    - `data_fetching_agent` records with raw text and face coordinates
    - `Unified_extractor` raw document results
    """

    extracted = dict(payload.get("extracted_data") or payload)
    front = dict(extracted.get("front_data") or {})
    back = dict(extracted.get("back_data") or {})

    doc_type = normalize_document_type(
        payload.get("document_type")
        or payload.get("doc_type")
        or extracted.get("document_type")
    )

    identity = IdentityDocumentData(
        document_type=doc_type,
        full_name=_first_present(extracted.get("full_name"), front.get("full_name")),
        full_name_en=_first_present(extracted.get("full_name_en"), front.get("full_name_en")),
        full_name_native=_first_present(extracted.get("full_name_native"), front.get("full_name_native")),
        father_name=extracted.get("father_name"),
        guardian_name=_first_present(extracted.get("guardian_name"), back.get("guardian_name")),
        date_of_birth=_coerce_date(_first_present(extracted.get("date_of_birth"), front.get("date_of_birth"))),
        year_of_birth=_first_present(extracted.get("year_of_birth"), front.get("year_of_birth")),
        gender=_first_present(extracted.get("gender"), front.get("gender")),
        aadhaar_number=_first_present(extracted.get("aadhaar_number"), front.get("aadhaar_number")),
        pan_number=extracted.get("pan_number"),
        address=_first_present(extracted.get("address"), back.get("address")),
        address_native=_first_present(extracted.get("address_native"), back.get("address_native")),
        pincode=_first_present(extracted.get("pincode"), back.get("pincode")),
    )

    extracted_data = identity.model_dump(exclude_none=True)
    for key, value in extracted.items():
        extracted_data.setdefault(key, value)

    return DocumentExtractionRecord(
        filename=payload.get("filename"),
        file_path=payload.get("path") or payload.get("file_path"),
        user_id=payload.get("user_id") or payload.get("unique_id"),
        document_type=doc_type,
        classification_confidence=float(payload.get("_classification_confidence", 0.0) or 0.0),
        extracted_data=extracted_data,
        raw_text_content=payload.get("raw_text_content") or payload.get("raw_text"),
        validation_status=extracted.get("validation_status") or payload.get("validation_status"),
        validation_errors=payload.get("validation_errors") or extracted.get("validation_errors") or [],
        face_coordinates=payload.get("face_coordinates") or payload.get("face_coords"),
        llm_repaired=payload.get("llm_repaired"),
    )


def adapt_unified_to_feature_user(record: DocumentExtractionRecord) -> FeatureEngineeringUserRecord:
    data = record.extracted_data
    user_name = _first_present(
        data.get("full_name_en"),
        data.get("full_name"),
        data.get("full_name_native"),
        record.user_id,
        "unknown_user",
    )

    return FeatureEngineeringUserRecord(
        user_name=str(user_name),
        date_of_birth=_coerce_date(data.get("date_of_birth")),
        is_aadhaar_verified=bool(data.get("aadhaar_number")),
        aadhaar_number=data.get("aadhaar_number"),
        aadhaar_gender=data.get("gender"),
        aadhaar_address=data.get("address"),
        is_pan_verified=bool(data.get("pan_number")),
        pan_number=data.get("pan_number"),
    )


def adapt_face_detection_result(
    detection: Mapping[str, Any],
    document_id: Optional[int],
    bbox_format: str = "xywh",
) -> FaceRecordContract:
    bbox = detection.get("bbox") or detection.get("coords") or [None, None, None, None]
    left = top = width = height = None
    if bbox and len(bbox) == 4:
        if bbox_format == "xyxy":
            x1, y1, x2, y2 = bbox
            left, top, width, height = int(x1), int(y1), int(x2) - int(x1), int(y2) - int(y1)
        else:
            left, top, width, height = [int(v) if v is not None else None for v in bbox]

    return FaceRecordContract(
        face_id=str(detection.get("face_id") or detection.get("id") or "unknown_face"),
        document_id=document_id,
        page_number=detection.get("page") or detection.get("page_number"),
        bbox_left=left,
        bbox_top=top,
        bbox_width=width,
        bbox_height=height,
        confidence=float(detection.get("confidence", 0.0) or 0.0),
        rotation_found=detection.get("rotation_found"),
        status="extracted" if left is not None else "failed",
        analysis_json=detection.get("analysis_json"),
    )


def adapt_face_verification_result(face: FaceRecordContract, result: Mapping[str, Any]) -> FaceRecordContract:
    updated = face.model_copy()
    same_person = bool(result.get("same_person"))
    updated.verification_result = "match" if same_person else "no_match"
    updated.verification_confidence = float(result.get("probability", result.get("confidence", 0.0)) or 0.0)
    return updated
