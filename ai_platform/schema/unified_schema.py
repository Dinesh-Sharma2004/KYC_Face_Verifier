"""Unified schema contracts mapped to existing repository contracts.

These Pydantic models are validation and adapter contracts. They do not create,
rename, or migrate PostgreSQL tables, SQLModel models, or Feast definitions.
"""

from typing import Literal, Optional

from pydantic import BaseModel


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
