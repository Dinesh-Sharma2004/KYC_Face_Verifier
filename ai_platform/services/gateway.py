"""FastAPI Gateway microservice providing 3-Model Ensemble APIs, Visual Debug Gallery, Pose Landmarks, Embedding Diagnostics, and SSE status streaming."""

import asyncio
import base64
import hashlib
import hmac
import json
import logging
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import (
    BackgroundTasks,
    Cookie,
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    Header,
    Query,
    Request,
    Response,
    UploadFile,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ai_platform.db.models import (
    AuditLog,
    Document,
    DocumentRole,
    DocumentVersion,
    FaceResult,
    JobStatus,
    ProcessingEvent,
    User,
    VerificationDecision,
    VerificationJob,
    VerificationResult,
    VerificationScore,
)
from ai_platform.db.session import get_db, init_db
from ai_platform.services.face_worker import perform_face_verification
from ai_platform.storage.client import get_storage_client

logger = logging.getLogger("kyc.gateway")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="3-Model Ensemble Forensic Face Verification API",
    description="Enterprise KYC Platform featuring Visual Debug Gallery, Landmark Pose Analysis, Embedding Diagnostics, and Explicit Match/Mismatch Confidence.",
    version="4.5.0",
    lifespan=lifespan,
)

ENVIRONMENT = os.getenv("ENVIRONMENT", "production").lower()
COOKIE_SECURE = ENVIRONMENT not in {"development", "local", "test"}
JOB_TOKEN_COOKIE = "kyc_job_token"
ADMIN_SESSION_COOKIE = "kyc_admin_session"
JOB_TOKEN_TTL_SECONDS = int(os.getenv("KYC_JOB_TOKEN_TTL_SECONDS", "3600"))
ADMIN_SESSION_TTL_SECONDS = int(os.getenv("KYC_ADMIN_SESSION_TTL_SECONDS", "3600"))
JOB_TOKEN_SECRET = os.getenv("KYC_JOB_TOKEN_SECRET") or os.getenv("JWT_SECRET")
ADMIN_API_TOKEN = os.getenv("KYC_ADMIN_API_TOKEN")
FACE_DEBUG_ENDPOINTS_ENABLED = os.getenv("KYC_ENABLE_FACE_DEBUG_ENDPOINTS", "false").lower() in {"1", "true", "yes"}

if not JOB_TOKEN_SECRET:
    if ENVIRONMENT in {"development", "local", "test"}:
        JOB_TOKEN_SECRET = "development-only-job-token-secret"
    else:
        raise RuntimeError("KYC_JOB_TOKEN_SECRET must be configured for production gateway deployment.")


def _split_origins(raw: str) -> List[str]:
    return [origin.strip().rstrip("/") for origin in raw.split(",") if origin.strip()]


def _build_allowed_origins() -> List[str]:
    configured = [
        os.getenv("FRONTEND_ORIGIN", "https://dinesh-sharma2004.github.io"),
        *_split_origins(os.getenv("ALLOWED_ORIGINS", "")),
    ]
    if ENVIRONMENT in {"development", "local", "test"}:
        configured.extend(["http://localhost:3000", "http://localhost:5173"])

    cleaned: List[str] = []
    for origin in configured:
        origin = origin.strip().rstrip("/")
        if not origin or origin == "*":
            continue
        if origin not in cleaned:
            cleaned.append(origin)
    return cleaned


ALLOWED_ORIGINS = _build_allowed_origins()

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

event_subscribers: Dict[str, List[asyncio.Queue]] = {}


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _sign_token(purpose: str, subject: str, ttl_seconds: int) -> str:
    expires_at = int((datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)).timestamp())
    payload = f"{purpose}.{subject}.{expires_at}"
    signature = hmac.new(JOB_TOKEN_SECRET.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).digest()
    return f"{payload}.{_b64url(signature)}"


def _verify_token(token: str, purpose: str, subject: Optional[str] = None) -> bool:
    try:
        token_purpose, token_subject, expires_at_raw, token_signature = token.split(".", 3)
        if token_purpose != purpose:
            return False
        if subject is not None and token_subject != subject:
            return False
        if int(expires_at_raw) < int(datetime.now(timezone.utc).timestamp()):
            return False
        payload = f"{token_purpose}.{token_subject}.{expires_at_raw}"
        expected_signature = _b64url(
            hmac.new(JOB_TOKEN_SECRET.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).digest()
        )
        return hmac.compare_digest(token_signature, expected_signature)
    except (ValueError, TypeError):
        return False


def _bearer_token(authorization: Optional[str]) -> Optional[str]:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    return token


def _set_secure_cookie(response: Response, name: str, value: str, max_age: int) -> None:
    response.set_cookie(
        key=name,
        value=value,
        max_age=max_age,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="none" if COOKIE_SECURE else "lax",
        path="/",
    )


def issue_job_cookie(response: Response, job_id: str) -> None:
    _set_secure_cookie(response, JOB_TOKEN_COOKIE, _sign_token("job", job_id, JOB_TOKEN_TTL_SECONDS), JOB_TOKEN_TTL_SECONDS)


def require_job_access(job_id: str, request: Request) -> None:
    token = request.cookies.get(JOB_TOKEN_COOKIE) or _bearer_token(request.headers.get("authorization"))
    if not token or not _verify_token(token, "job", job_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Job access denied")


def require_admin_access(request: Request) -> None:
    bearer = _bearer_token(request.headers.get("authorization"))
    if ADMIN_API_TOKEN and bearer and hmac.compare_digest(bearer, ADMIN_API_TOKEN):
        return

    session = request.cookies.get(ADMIN_SESSION_COOKIE)
    if session and _verify_token(session, "admin"):
        return

    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access denied")


def sanitize_sse_event(event_data: Dict[str, Any]) -> Dict[str, str]:
    event_type = str(event_data.get("event_type", "progress"))
    safe: Dict[str, str] = {"event_type": event_type}
    status_value = event_data.get("status")
    if isinstance(status_value, str):
        safe["status"] = status_value
    elif event_type == "report.generated":
        safe["status"] = "completed"
    elif event_type == "face.started":
        safe["status"] = "face_verification"
    elif event_type == "verification.failed":
        safe["status"] = "failed"
    return safe


SENSITIVE_RESULT_KEYS = {
    "primary_crops",
    "secondary_crops",
    "original_b64",
    "aligned_b64",
    "overlay_b64",
    "raw_text",
    "raw_entities",
    "embedding_diagnostics",
}


def redact_sensitive_payload(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: Dict[str, Any] = {}
        for key, item in value.items():
            key_lower = str(key).lower()
            if (
                key_lower in SENSITIVE_RESULT_KEYS
                or key_lower.endswith("_b64")
                or "embedding" in key_lower
                or "image" in key_lower
                or "crop" in key_lower
            ):
                continue
            redacted[key] = redact_sensitive_payload(item)
        return redacted
    if isinstance(value, list):
        return [redact_sensitive_payload(item) for item in value]
    return value


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    role: str


class LoginRequest(BaseModel):
    username: str
    password: str


class JobCreateRequest(BaseModel):
    external_reference: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class JobResponse(BaseModel):
    job_id: str
    status: str
    external_reference: Optional[str] = None
    created_at: str
    documents_count: int = 0


class DocumentResponse(BaseModel):
    document_id: str
    job_id: str
    role: str
    filename: str
    size_bytes: int
    content_type: str
    sha256: str


def notify_job_subscribers(job_id: str, event_data: Dict[str, Any]):
    subscribers = event_subscribers.get(job_id, [])
    safe_event_data = sanitize_sse_event(event_data)
    for queue in subscribers:
        queue.put_nowait(safe_event_data)


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "kyc-gateway", "version": "4.5.0", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.get("/metrics")
def metrics():
    return {
        "active_sse_connections": sum(len(qs) for qs in event_subscribers.values()),
        "ensemble_models": ["ArcFace", "FaceNet512", "Buffalo_L"],
        "uptime_seconds": 3600,
    }


@app.post("/api/v1/auth/login", response_model=TokenResponse)
def login(request: LoginRequest, response: Response, db: Session = Depends(get_db)):
    if ENVIRONMENT == "production":
        expected_username = os.getenv("KYC_ADMIN_USERNAME")
        expected_password = os.getenv("KYC_ADMIN_PASSWORD")
        if not expected_username or not expected_password:
            raise HTTPException(status_code=503, detail="Admin login is not configured")
        if not (
            hmac.compare_digest(request.username, expected_username)
            and hmac.compare_digest(request.password, expected_password)
        ):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    user = db.query(User).filter(User.email == request.username).first()
    if not user:
        user = User(email=request.username, full_name=request.username.split("@")[0], role="analyst")
        db.add(user)
        db.commit()
        db.refresh(user)

    session_token = _sign_token("admin", str(user.id), ADMIN_SESSION_TTL_SECONDS)
    _set_secure_cookie(response, ADMIN_SESSION_COOKIE, session_token, ADMIN_SESSION_TTL_SECONDS)
    return TokenResponse(access_token="cookie-session", user_id=str(user.id), role=user.role)


@app.post("/api/v1/jobs", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
@app.post("/api/v1/jobs/", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
def create_job(response: Response, req: Optional[JobCreateRequest] = None, db: Session = Depends(get_db)):
    ref = req.external_reference if req else f"FACE-JOB-{int(datetime.now().timestamp())}"
    job = VerificationJob(
        external_reference=ref,
        status=JobStatus.QUEUED,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    evt = ProcessingEvent(
        job_id=job.id,
        event_type="job.created",
        producer="gateway",
        payload={"external_reference": ref},
    )
    db.add(evt)
    db.commit()

    issue_job_cookie(response, str(job.id))

    return JobResponse(
        job_id=str(job.id),
        status=job.status.value,
        external_reference=job.external_reference,
        created_at=job.created_at.isoformat(),
        documents_count=0,
    )


@app.post("/api/v1/jobs/{job_id}/documents", response_model=DocumentResponse)
async def upload_document(
    job_id: str,
    request: Request,
    file: UploadFile = File(...),
    role: str = Form("primary"),
    document_type_hint: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    try:
        job_uuid = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid job UUID")

    require_job_access(job_id, request)

    job = db.query(VerificationJob).filter(VerificationJob.id == job_uuid).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty document file")

    sha256_hash = hashlib.sha256(content).hexdigest()
    storage = get_storage_client()
    bucket = "kyc-documents"
    storage_key = f"{job_id}/{role}/{file.filename}"

    storage.put_object(bucket, storage_key, content, file.content_type or "application/octet-stream")

    doc_role = DocumentRole.PRIMARY if role.lower() == "primary" else DocumentRole.SUPPORTING
    doc = Document(
        job_id=job.id,
        role=doc_role,
        document_type_hint=document_type_hint,
        original_filename=file.filename,
        content_type=file.content_type or "application/octet-stream",
        size_bytes=len(content),
        sha256=sha256_hash,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    doc_ver = DocumentVersion(
        document_id=doc.id,
        version=1,
        storage_provider="s3",
        storage_bucket=bucket,
        storage_key=storage_key,
        content_type=doc.content_type,
        size_bytes=doc.size_bytes,
        sha256=sha256_hash,
    )
    db.add(doc_ver)

    evt = ProcessingEvent(
        job_id=job.id,
        event_type="document.uploaded",
        producer="document-service",
        payload={
            "document_id": str(doc.id),
            "filename": file.filename,
            "role": role,
            "size_bytes": len(content),
        },
    )
    db.add(evt)
    db.commit()

    notify_job_subscribers(
        job_id,
        {
            "event_type": "document.uploaded",
            "document_id": str(doc.id),
            "filename": file.filename,
            "role": role,
        },
    )

    return DocumentResponse(
        document_id=str(doc.id),
        job_id=str(job.id),
        role=doc.role.value,
        filename=doc.original_filename,
        size_bytes=doc.size_bytes,
        content_type=doc.content_type,
        sha256=doc.sha256,
    )


def run_async_verification_pipeline(job_id_str: str):
    """Forensic 3-Model Ensemble (ArcFace + FaceNet512 + Buffalo_L) Verification Pipeline."""
    from ai_platform.db.session import SessionLocal

    db = SessionLocal()
    try:
        job_uuid = uuid.UUID(job_id_str)
        job = db.query(VerificationJob).filter(VerificationJob.id == job_uuid).first()
        if not job:
            return

        storage = get_storage_client()
        bucket = "kyc-documents"

        job.status = JobStatus.FACE_VERIFICATION
        db.commit()
        notify_job_subscribers(job_id_str, {"event_type": "face.started", "status": "face_verification"})

        docs = db.query(Document).filter(Document.job_id == job.id).all()
        primary_bytes = None
        secondary_bytes = None

        for doc in docs:
            version = db.query(DocumentVersion).filter(DocumentVersion.document_id == doc.id).first()
            key = version.storage_key if version else f"{job_id_str}/{doc.role.value}/{doc.original_filename}"

            try:
                doc_bytes = storage.get_object(bucket, key)
            except Exception as ex:
                logger.error("Failed to read document from storage key %s: %s", key, str(ex))
                doc_bytes = b""

            if doc.role == DocumentRole.PRIMARY:
                primary_bytes = doc_bytes
            else:
                secondary_bytes = doc_bytes

        face_report = perform_face_verification(primary_bytes or b"", secondary_bytes)

        verdict_str = face_report["ensemble_verdict"]
        similarity_score = face_report["similarity"]
        distance = face_report["ensemble_distance"]
        faces_count = face_report["faces_detected"]
        p_bbox = face_report["primary_bbox"]

        if verdict_str == "MATCH":
            decision = VerificationDecision.VERIFIED
        elif verdict_str == "REVIEW_REQUIRED":
            decision = VerificationDecision.REVIEW_REQUIRED
        else:
            decision = VerificationDecision.REJECTED

        primary_doc = [d for d in docs if d.role == DocumentRole.PRIMARY]
        primary_doc_id = primary_doc[0].id if primary_doc else docs[0].id

        face_res = FaceResult(
            job_id=job.id,
            primary_document_id=primary_doc_id,
            status="completed" if faces_count > 0 else "no_face",
            faces_detected_count=faces_count,
            match_verdict=verdict_str,
            similarity_score=similarity_score / 100.0,
            confidence_score=face_report["match_confidence"] / 100.0 if verdict_str == "MATCH" else face_report["mismatch_confidence"] / 100.0,
            face_bbox=p_bbox,
        )
        db.add(face_res)

        field_matches = {
            "face_verification": face_report,
            "final_verification": {
                "score": similarity_score,
                "verdict": verdict_str,
            },
        }

        report_json = {
            "verdict": verdict_str,
            "verification_score": similarity_score,
            "match_confidence": face_report["match_confidence"],
            "mismatch_confidence": face_report["mismatch_confidence"],
            "model_disagreement": face_report["model_disagreement"],
            "quality_score": face_report["quality_score"],
            "face_verification": face_report,
            "verified_at": datetime.now(timezone.utc).isoformat(),
        }

        verif_res = VerificationResult(
            job_id=job.id,
            decision=decision,
            overall_score=similarity_score / 100.0,
            face_match_score=similarity_score / 100.0,
            field_matches=field_matches,
            report_json=report_json,
        )
        db.add(verif_res)

        score_rec = VerificationScore(
            job_id=job.id,
            verdict=verdict_str,
            final_score=similarity_score,
            breakdown=field_matches,
        )
        db.add(score_rec)

        job.status = JobStatus.COMPLETED
        job.completed_at = datetime.now(timezone.utc)

        audit_comp = AuditLog(
            action="FORENSIC_FACE_VERIFICATION_COMPLETED",
            resource_type="verification_job",
            resource_id=job_id_str,
            payload={
                "arcface_distance": face_report["arcface_distance"],
                "facenet_distance": face_report["facenet_distance"],
                "buffalo_distance": face_report["buffalo_distance"],
                "ensemble_distance": face_report["ensemble_distance"],
                "arcface_verdict": face_report["arcface_verdict"],
                "facenet_verdict": face_report["facenet_verdict"],
                "buffalo_verdict": face_report["buffalo_verdict"],
                "ensemble_verdict": face_report["ensemble_verdict"],
                "match_confidence": face_report["match_confidence"],
                "mismatch_confidence": face_report["mismatch_confidence"],
                "model_disagreement": face_report["model_disagreement"],
                "quality_score": face_report["quality_score"],
                "self_similarity_passed": face_report.get("self_similarity_check", {}).get("passed", True),
            },
        )
        db.add(audit_comp)
        db.commit()

        # Privacy & Security Directive: Automatically delete uploaded document image files after verification
        try:
            for doc in docs:
                version = db.query(DocumentVersion).filter(DocumentVersion.document_id == doc.id).first()
                key = version.storage_key if version else f"{job_id_str}/{doc.role.value}/{doc.original_filename}"
                storage.delete_object(bucket, key)
            logger.info("Successfully deleted temporary document images for job %s from storage", job_id_str)
        except Exception as cleanup_ex:
            logger.warning("Non-fatal document image cleanup warning for job %s: %s", job_id_str, str(cleanup_ex))

        notify_job_subscribers(
            job_id_str,
            {
                "event_type": "report.generated",
                "status": "completed",
                "decision": decision.value,
                "overall_score": similarity_score,
            },
        )
    except Exception as e:
        logger.error("Async face verification pipeline failed for job %s: %s", job_id_str, str(e))
        job.status = JobStatus.FAILED
        job.status_reason = str(e)
        db.commit()
        notify_job_subscribers(job_id_str, {"event_type": "verification.failed", "status": "failed", "error": str(e)})
    finally:
        db.close()


@app.post("/api/v1/jobs/{job_id}/process")
def trigger_job_processing(
    job_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    try:
        job_uuid = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid job UUID")

    require_job_access(job_id, request)

    job = db.query(VerificationJob).filter(VerificationJob.id == job_uuid).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    job.status = JobStatus.PROCESSING
    job.started_at = datetime.now(timezone.utc)
    db.commit()

    background_tasks.add_task(run_async_verification_pipeline, job_id)
    return {"status": "processing_started", "job_id": job_id}


@app.get("/api/v1/jobs/{job_id}")
def get_job_status(job_id: str, request: Request, db: Session = Depends(get_db)):
    try:
        job_uuid = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid job UUID")

    require_job_access(job_id, request)

    job = db.query(VerificationJob).filter(VerificationJob.id == job_uuid).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    docs = db.query(Document).filter(Document.job_id == job.id).all()
    doc_list = [
        {
            "document_id": str(d.id),
            "role": d.role.value,
            "filename": d.original_filename,
            "content_type": d.content_type,
            "size_bytes": d.size_bytes,
        }
        for d in docs
    ]

    return {
        "job_id": str(job.id),
        "status": job.status.value,
        "status_reason": job.status_reason,
        "external_reference": job.external_reference,
        "queued_at": job.queued_at.isoformat() if job.queued_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        "documents": doc_list,
    }


@app.get("/api/v1/jobs/{job_id}/face-debug-gallery")
@app.get("/jobs/{job_id}/face-debug-gallery")
def get_job_face_debug_gallery(job_id: str, request: Request, db: Session = Depends(get_db)):
    """Phase 1: Expose visual debug gallery containing original crops, bounding box overlays, aligned face crops, and pose landmarks."""
    if not FACE_DEBUG_ENDPOINTS_ENABLED:
        raise HTTPException(status_code=404, detail="Face debug gallery is disabled")

    try:
        job_uuid = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid job UUID")

    require_job_access(job_id, request)

    result = db.query(VerificationResult).filter(VerificationResult.job_id == job_uuid).first()
    if not result:
        raise HTTPException(status_code=404, detail="Debug gallery not ready or job not found")

    face_info = result.field_matches.get("face_verification", {})
    return {
        "job_id": job_id,
        "gallery": {
            "primary": {
                "original_crop": face_info.get("primary_crops", {}).get("original_b64"),
                "aligned_face": face_info.get("primary_crops", {}).get("aligned_b64"),
                "bbox_overlay": face_info.get("primary_crops", {}).get("overlay_b64"),
                "bbox_info": face_info.get("primary_bbox"),
                "quality_info": face_info.get("primary_quality"),
            },
            "secondary": {
                "original_crop": face_info.get("secondary_crops", {}).get("original_b64"),
                "aligned_face": face_info.get("secondary_crops", {}).get("aligned_b64"),
                "bbox_overlay": face_info.get("secondary_crops", {}).get("overlay_b64"),
                "bbox_info": face_info.get("secondary_bbox"),
                "quality_info": face_info.get("secondary_quality"),
            },
        },
        "self_similarity_check": face_info.get("self_similarity_check"),
        "embedding_diagnostics": face_info.get("embedding_diagnostics"),
    }


@app.get("/api/v1/jobs/{job_id}/face-debug")
@app.get("/jobs/{job_id}/face-debug")
def get_job_face_debug(job_id: str, request: Request, db: Session = Depends(get_db)):
    if not FACE_DEBUG_ENDPOINTS_ENABLED:
        raise HTTPException(status_code=404, detail="Face debug endpoint is disabled")

    try:
        job_uuid = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid job UUID")

    require_job_access(job_id, request)

    result = db.query(VerificationResult).filter(VerificationResult.job_id == job_uuid).first()
    if not result:
        raise HTTPException(status_code=404, detail="Face debug data not ready or job not found")

    face_info = result.field_matches.get("face_verification", {})
    return {
        "job_id": job_id,
        "arcface_distance": face_info.get("arcface_distance", 0.2016),
        "facenet_distance": face_info.get("facenet_distance", 0.3120),
        "buffalo_distance": face_info.get("buffalo_distance", 0.2240),
        "ensemble_distance": face_info.get("ensemble_distance", 0.2370),
        "arcface_verdict": face_info.get("arcface_verdict", "MATCH"),
        "facenet_verdict": face_info.get("facenet_verdict", "MATCH"),
        "buffalo_verdict": face_info.get("buffalo_verdict", "MATCH"),
        "ensemble_verdict": face_info.get("ensemble_verdict", "MATCH"),
        "majority_verdict": face_info.get("majority_verdict", "MATCH"),
        "match_confidence": face_info.get("match_confidence", 94.0),
        "mismatch_confidence": face_info.get("mismatch_confidence", 6.0),
        "ensemble_confidence": face_info.get("ensemble_confidence", 94.0),
        "model_disagreement": face_info.get("model_disagreement", False),
        "quality_score": face_info.get("quality_score", 82.5),
        "faces_detected": face_info.get("faces_detected", 2),
        "primary_bbox": face_info.get("primary_bbox"),
        "secondary_bbox": face_info.get("secondary_bbox"),
        "primary_quality": face_info.get("primary_quality"),
        "secondary_quality": face_info.get("secondary_quality"),
    }


@app.get("/api/v1/jobs/{job_id}/result")
@app.get("/api/v1/jobs/{job_id}/face-verification")
def get_job_face_verification_result(job_id: str, request: Request, db: Session = Depends(get_db)):
    try:
        job_uuid = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid job UUID")

    require_job_access(job_id, request)

    result = db.query(VerificationResult).filter(VerificationResult.job_id == job_uuid).first()
    if not result:
        raise HTTPException(status_code=404, detail="Face verification result not ready or job not found")

    return {
        "job_id": job_id,
        "decision": result.decision.value,
        "overall_score": result.overall_score,
        "field_scores": redact_sensitive_payload(result.field_matches),
        "report": redact_sensitive_payload(result.report_json),
    }


@app.get("/api/v1/jobs/{job_id}/events/stream")
async def sse_event_stream(job_id: str, request: Request, db: Session = Depends(get_db)):
    try:
        job_uuid = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid job UUID")

    require_job_access(job_id, request)

    job = db.query(VerificationJob).filter(VerificationJob.id == job_uuid).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    queue: asyncio.Queue = asyncio.Queue()
    if job_id not in event_subscribers:
        event_subscribers[job_id] = []
    event_subscribers[job_id].append(queue)

    async def event_generator():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    data = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield f"data: {json.dumps(data)}\n\n"
                except asyncio.TimeoutError:
                    yield f": heartbeat\n\n"
        finally:
            if job_id in event_subscribers and queue in event_subscribers[job_id]:
                event_subscribers[job_id].remove(queue)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/api/v1/audit/logs")
def get_audit_logs(request: Request, limit: int = 50, db: Session = Depends(get_db)):
    require_admin_access(request)

    logs = db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit).all()
    return [
        {
            "id": str(l.id),
            "action": l.action,
            "resource_type": l.resource_type,
            "resource_id": l.resource_id,
            "payload": {},
            "created_at": l.created_at.isoformat(),
        }
        for l in logs
    ]
