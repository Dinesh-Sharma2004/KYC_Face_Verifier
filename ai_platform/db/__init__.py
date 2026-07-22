"""Database package initialization."""

from ai_platform.db.models import (
    AuditLog,
    Base,
    Document,
    DocumentRole,
    ExtractedEntity,
    FaceResult,
    JobStatus,
    NormalizedEntity,
    OcrResult,
    ProcessingEvent,
    User,
    VerificationDecision,
    VerificationJob,
    VerificationResult,
    VerificationScore,
)
from ai_platform.db.session import SessionLocal, get_db, init_db

__all__ = [
    "Base",
    "User",
    "VerificationJob",
    "Document",
    "OcrResult",
    "FaceResult",
    "VerificationResult",
    "AuditLog",
    "ProcessingEvent",
    "DocumentRole",
    "JobStatus",
    "VerificationDecision",
    "SessionLocal",
    "get_db",
    "init_db",
]
