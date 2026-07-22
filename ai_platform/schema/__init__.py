"""Unified schema contracts and adapters."""

from .legacy_adapters import (
    adapt_face_detection_result,
    adapt_face_verification_result,
    adapt_legacy_identity_document,
    adapt_unified_to_feature_user,
)
from .unified_schema import (
    CreditScoreFeatureRecord,
    DocumentExtractionRecord,
    FaceDocumentRecord,
    FaceRecordContract,
    FeatureEngineeringUserRecord,
    IdentityDocumentData,
    UnifiedDocumentType,
)

__all__ = [
    "CreditScoreFeatureRecord",
    "DocumentExtractionRecord",
    "FaceDocumentRecord",
    "FaceRecordContract",
    "FeatureEngineeringUserRecord",
    "IdentityDocumentData",
    "UnifiedDocumentType",
    "adapt_face_detection_result",
    "adapt_face_verification_result",
    "adapt_legacy_identity_document",
    "adapt_unified_to_feature_user",
]
