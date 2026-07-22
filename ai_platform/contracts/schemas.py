"""Canonical Pydantic contracts for cross-service payloads.

These contracts consolidate the strongest discovered schemas without changing
the existing PostgreSQL or Feast contracts. Database table definitions remain in
their current owning services until a single migration authority is introduced.
"""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Dict, List, Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class DocumentType(StrEnum):
    TAX_INVOICE = "TAX_INVOICE"
    BANK_STATEMENT = "BANK_STATEMENT"
    SALARY_SLIP = "SALARY_SLIP"
    AADHAAR_CARD = "AADHAAR_CARD"
    PAN_CARD = "PAN_CARD"
    SALE_DEED = "SALE_DEED"
    HAKKU_PATRA = "HAKKU_PATRA"
    KHATA_CERTIFICATE = "KHATA_CERTIFICATE"
    POSSESSION_CERTIFICATE = "POSSESSION_CERTIFICATE"
    PROPERTY_TAX_RECEIPT = "PROPERTY_TAX_RECEIPT"
    UNKNOWN = "UNKNOWN"


class AgentStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    RETRYING = "retrying"
    SKIPPED = "skipped"


class UploadedDocument(BaseModel):
    document_id: Optional[str] = None
    filename: str
    file_path: str
    document_type: DocumentType = DocumentType.UNKNOWN
    classification_confidence: float = 0.0
    user_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ExtractedDocument(BaseModel):
    document: UploadedDocument
    extracted_data: Dict[str, Any] = Field(default_factory=dict)
    raw_text: Optional[str] = None
    validation_status: Optional[str] = None
    errors: List[str] = Field(default_factory=list)


class FaceVerificationResult(BaseModel):
    document_id: Optional[str] = None
    face_id: Optional[str] = None
    same_person: Optional[bool] = None
    confidence: Optional[float] = None
    verification_result: Optional[Literal["match", "no_match"]] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AgentExecutionTrace(BaseModel):
    trace_id: str
    job_id: str
    agent_name: str
    start_time: datetime
    end_time: Optional[datetime] = None
    execution_time_ms: Optional[float] = None
    success: bool = False
    failure_reason: Optional[str] = None
    retries: int = 0
    tool_calls: List[Dict[str, Any]] = Field(default_factory=list)
    token_usage: Dict[str, int] = Field(default_factory=dict)
    cost_estimation: Dict[str, float] = Field(default_factory=dict)


class PlatformJob(BaseModel):
    job_id: str = Field(default_factory=lambda: str(uuid4()))
    trace_id: str = Field(default_factory=lambda: str(uuid4()))
    user_id: Optional[str] = None
    status: AgentStatus = AgentStatus.PENDING
    documents: List[UploadedDocument] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class WorkflowState(BaseModel):
    job: PlatformJob
    extracted_documents: List[ExtractedDocument] = Field(default_factory=list)
    face_results: List[FaceVerificationResult] = Field(default_factory=list)
    engineered_features: Dict[str, Any] = Field(default_factory=dict)
    model_output: Dict[str, Any] = Field(default_factory=dict)
    traces: List[AgentExecutionTrace] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
