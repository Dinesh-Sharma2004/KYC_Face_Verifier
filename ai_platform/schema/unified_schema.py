"""Unified schema contracts mapped to existing repository contracts.

These Pydantic models are validation and adapter contracts. They do not create,
rename, or migrate PostgreSQL tables, SQLModel models, or Feast definitions.
"""

from datetime import date, datetime
from enum import StrEnum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class UnifiedDocumentType(StrEnum):
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


class IdentityDocumentData(BaseModel):
    """Common PAN/Aadhaar fields across legacy and unified extractors."""

    model_config = ConfigDict(extra="allow")

    document_type: UnifiedDocumentType = UnifiedDocumentType.UNKNOWN
    full_name: Optional[str] = None
    full_name_en: Optional[str] = None
    full_name_native: Optional[str] = None
    father_name: Optional[str] = None
    guardian_name: Optional[str] = None
    date_of_birth: Optional[date | str] = None
    year_of_birth: Optional[int] = None
    gender: Optional[str] = None
    aadhaar_number: Optional[str] = None
    pan_number: Optional[str] = None
    address: Optional[str] = None
    address_native: Optional[str] = None
    pincode: Optional[str] = None


class DocumentExtractionRecord(BaseModel):
    """Unified extraction payload preserving existing field names."""

    model_config = ConfigDict(extra="allow")

    filename: Optional[str] = None
    file_path: Optional[str] = None
    user_id: Optional[str] = None
    document_type: UnifiedDocumentType = UnifiedDocumentType.UNKNOWN
    classification_confidence: float = 0.0
    extracted_data: Dict[str, Any] = Field(default_factory=dict)
    raw_text_content: Optional[str] = None
    validation_status: Optional[str] = None
    validation_errors: List[str] = Field(default_factory=list)
    face_coordinates: Optional[Dict[str, Any]] = None
    llm_repaired: Optional[Dict[str, Any]] = None


class FaceDocumentRecord(BaseModel):
    """Mirror of `5_face_verification.app.models.Document`."""

    id: Optional[int] = None
    url: str
    filename: str
    file_path: str
    created_at: Optional[float] = None


class FaceRecordContract(BaseModel):
    """Mirror of `5_face_verification.app.models.FaceRecord`."""

    id: Optional[int] = None
    face_id: str
    document_id: Optional[int] = None
    page_number: Optional[int] = None
    bbox_left: Optional[int] = None
    bbox_top: Optional[int] = None
    bbox_width: Optional[int] = None
    bbox_height: Optional[int] = None
    confidence: Optional[float] = None
    rotation_found: Optional[str] = None
    status: str = "pending"
    analysis_json: Optional[str] = None
    verification_result: Optional[Literal["match", "no_match"]] = None
    verification_confidence: Optional[float] = None


class FeatureEngineeringUserRecord(BaseModel):
    """Mirror of the SQLAlchemy `users` table in feature engineering."""

    user_name: str
    date_of_birth: Optional[date | str] = None
    age: Optional[int] = None
    is_aadhaar_verified: bool = False
    aadhaar_number: Optional[str] = None
    aadhaar_gender: Optional[str] = None
    aadhaar_address: Optional[str] = None
    is_pan_verified: bool = False
    pan_number: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class CreditScoreFeatureRecord(BaseModel):
    """Mirror of Feast `credit_score_features` source query."""

    applicant_id: str
    age: int
    income: float
    credit_history_length: int
    number_of_loans: int
    loan_amount: float
    default_history: str
    submission_date: datetime


class AgentTraceRecord(BaseModel):
    """Trace payload required by agent/MCP/workflow execution."""

    trace_id: str
    job_id: str
    agent_name: str
    start_time: datetime
    end_time: Optional[datetime] = None
    execution_time_ms: Optional[float] = None
    success: bool
    failure_reason: Optional[str] = None
    retries: int = 0
    tool_calls: List[Dict[str, Any]] = Field(default_factory=list)
    token_usage: Dict[str, int] = Field(default_factory=dict)
    cost_estimation: Dict[str, float] = Field(default_factory=dict)
