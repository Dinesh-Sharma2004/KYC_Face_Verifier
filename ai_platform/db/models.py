"""Database ORM models matching schema.sql specifications."""

import enum
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import JSON, TypeDecorator


class Base(DeclarativeBase):
    pass


class JSONType(TypeDecorator):
    """Platform generic JSON type that falls back to JSON on SQLite and JSONB on Postgres."""

    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(JSONB())
        return dialect.type_descriptor(JSON())


class UUIDType(TypeDecorator):
    """Platform generic UUID type for Postgres UUID and String on SQLite."""

    impl = String(36)
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(UUID(as_uuid=True))
        return dialect.type_descriptor(String(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, uuid.UUID):
            return value
        return uuid.UUID(str(value))


class DocumentRole(str, enum.Enum):
    PRIMARY = "primary"
    SUPPORTING = "supporting"


class JobStatus(str, enum.Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    OCR_RUNNING = "ocr_running"
    FACE_VERIFICATION = "face_verification"
    MATCHING = "matching"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class VerificationDecision(str, enum.Enum):
    VERIFIED = "verified"
    REVIEW_REQUIRED = "review_required"
    REJECTED = "rejected"
    FAILED = "failed"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def gen_uuid() -> uuid.UUID:
    return uuid.uuid4()


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=gen_uuid)
    email: Mapped[Optional[str]] = mapped_column(String, unique=True, nullable=True)
    full_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    role: Mapped[str] = mapped_column(String, default="analyst", nullable=False)
    tenant_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUIDType, nullable=True)
    password_hash: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    jobs = relationship("VerificationJob", back_populates="user")


class VerificationJob(Base):
    __tablename__ = "verification_jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=gen_uuid)
    tenant_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUIDType, nullable=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUIDType, ForeignKey("users.id"), nullable=False)
    external_reference: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    status: Mapped[JobStatus] = mapped_column(Enum(JobStatus), default=JobStatus.QUEUED, nullable=False)
    status_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    trace_id: Mapped[uuid.UUID] = mapped_column(UUIDType, default=gen_uuid, nullable=False)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String, unique=True, nullable=True)
    queued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="jobs")
    documents = relationship("Document", back_populates="job", cascade="all, delete-orphan")
    ocr_results = relationship("OcrResult", back_populates="job", cascade="all, delete-orphan")
    face_results = relationship("FaceResult", back_populates="job", cascade="all, delete-orphan")
    verification_results = relationship("VerificationResult", back_populates="job", cascade="all, delete-orphan")
    events = relationship("ProcessingEvent", back_populates="job", cascade="all, delete-orphan")


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=gen_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(UUIDType, ForeignKey("users.id"), nullable=False)
    job_id: Mapped[uuid.UUID] = mapped_column(UUIDType, ForeignKey("verification_jobs.id"), nullable=False)
    tenant_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUIDType, nullable=True)
    role: Mapped[DocumentRole] = mapped_column(Enum(DocumentRole), nullable=False)
    document_type_hint: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    detected_document_type: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    original_filename: Mapped[str] = mapped_column(String, nullable=False)
    content_type: Mapped[str] = mapped_column(String, nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(String, nullable=False)
    file_content: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    current_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    metadata_json: Mapped[Dict[str, Any]] = mapped_column("metadata", JSONType, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    job = relationship("VerificationJob", back_populates="documents")



class OcrResult(Base):
    __tablename__ = "ocr_results"

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=gen_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(UUIDType, ForeignKey("users.id"), nullable=False)
    job_id: Mapped[uuid.UUID] = mapped_column(UUIDType, ForeignKey("verification_jobs.id"), nullable=False)
    document_id: Mapped[uuid.UUID] = mapped_column(UUIDType, ForeignKey("documents.id"), nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    engine: Mapped[str] = mapped_column(String, nullable=False)
    engine_version: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    raw_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    extracted_data: Mapped[Dict[str, Any]] = mapped_column(JSONType, default=dict, nullable=False)
    confidence_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    quality_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    job = relationship("VerificationJob", back_populates="ocr_results")


class FaceResult(Base):
    __tablename__ = "face_results"

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=gen_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(UUIDType, ForeignKey("users.id"), nullable=False)
    job_id: Mapped[uuid.UUID] = mapped_column(UUIDType, ForeignKey("verification_jobs.id"), nullable=False)
    primary_document_id: Mapped[uuid.UUID] = mapped_column(UUIDType, ForeignKey("documents.id"), nullable=False)
    secondary_document_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUIDType, ForeignKey("documents.id"), nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False)
    faces_detected_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    match_verdict: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    similarity_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    confidence_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    face_bbox: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONType, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    job = relationship("VerificationJob", back_populates="face_results")


class VerificationResult(Base):
    __tablename__ = "verification_results"

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=gen_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(UUIDType, ForeignKey("users.id"), nullable=False)
    job_id: Mapped[uuid.UUID] = mapped_column(UUIDType, ForeignKey("verification_jobs.id"), nullable=False)
    decision: Mapped[VerificationDecision] = mapped_column(Enum(VerificationDecision), nullable=False)
    overall_score: Mapped[float] = mapped_column(Float, nullable=False)
    name_match_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    dob_match_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    address_match_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    id_number_match_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    face_match_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    field_matches: Mapped[Dict[str, Any]] = mapped_column(JSONType, default=dict, nullable=False)
    report_json: Mapped[Dict[str, Any]] = mapped_column(JSONType, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    job = relationship("VerificationJob", back_populates="verification_results")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=gen_uuid)
    tenant_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUIDType, nullable=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUIDType, ForeignKey("users.id"), nullable=False)
    action: Mapped[str] = mapped_column(String, nullable=False)
    resource_type: Mapped[str] = mapped_column(String, nullable=False)
    resource_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    payload: Mapped[Dict[str, Any]] = mapped_column(JSONType, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class ProcessingEvent(Base):
    __tablename__ = "processing_events"

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=gen_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(UUIDType, ForeignKey("users.id"), nullable=False)
    job_id: Mapped[uuid.UUID] = mapped_column(UUIDType, ForeignKey("verification_jobs.id"), nullable=False)
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    producer: Mapped[str] = mapped_column(String, nullable=False)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    payload: Mapped[Dict[str, Any]] = mapped_column(JSONType, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    job = relationship("VerificationJob", back_populates="events")


class ExtractedEntity(Base):
    __tablename__ = "extracted_entities"

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=gen_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(UUIDType, ForeignKey("users.id"), nullable=False)
    job_id: Mapped[uuid.UUID] = mapped_column(UUIDType, ForeignKey("verification_jobs.id"), nullable=False)
    document_id: Mapped[uuid.UUID] = mapped_column(UUIDType, ForeignKey("documents.id"), nullable=False)
    document_type: Mapped[str] = mapped_column(String, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    raw_entities: Mapped[Dict[str, Any]] = mapped_column(JSONType, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class NormalizedEntity(Base):
    __tablename__ = "normalized_entities"

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=gen_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(UUIDType, ForeignKey("users.id"), nullable=False)
    job_id: Mapped[uuid.UUID] = mapped_column(UUIDType, ForeignKey("verification_jobs.id"), nullable=False)
    document_id: Mapped[uuid.UUID] = mapped_column(UUIDType, ForeignKey("documents.id"), nullable=False)
    extracted_entity_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUIDType, ForeignKey("extracted_entities.id"), nullable=True)
    normalized_entities: Mapped[Dict[str, Any]] = mapped_column(JSONType, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class VerificationScore(Base):
    __tablename__ = "verification_scores"

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=gen_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(UUIDType, ForeignKey("users.id"), nullable=False)
    job_id: Mapped[uuid.UUID] = mapped_column(UUIDType, ForeignKey("verification_jobs.id"), nullable=False)
    verdict: Mapped[str] = mapped_column(String, nullable=False)
    final_score: Mapped[float] = mapped_column(Float, nullable=False)
    breakdown: Mapped[Dict[str, Any]] = mapped_column(JSONType, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

