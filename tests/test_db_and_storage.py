"""Unit tests for Database ORM models, session layer, and StorageClient implementations."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from ai_platform.db.models import (
    Base,
    Document,
    DocumentRole,
    DocumentVersion,
    JobStatus,
    User,
    VerificationDecision,
    VerificationJob,
    VerificationResult,
)
from ai_platform.storage.client import LocalStorageClient, StorageClient


@pytest.fixture
def db_session():
    """Create in-memory SQLite database session for unit testing."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_user_and_job_lifecycle(db_session):
    user = User(email="test@example.com", full_name="Test User", role="analyst")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    assert user.id is not None
    assert user.role == "analyst"

    job = VerificationJob(user_id=user.id, status=JobStatus.QUEUED)
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    assert job.id is not None
    assert job.status == JobStatus.QUEUED
    assert job.user_id == user.id


def test_document_and_version_creation(db_session):
    job = VerificationJob(status=JobStatus.PROCESSING)
    db_session.add(job)
    db_session.commit()

    doc = Document(
        job_id=job.id,
        role=DocumentRole.PRIMARY,
        document_type_hint="PAN_CARD",
        original_filename="pan.pdf",
        content_type="application/pdf",
        size_bytes=1024,
        sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    )
    db_session.add(doc)
    db_session.commit()

    doc_version = DocumentVersion(
        document_id=doc.id,
        version=1,
        storage_provider="minio",
        storage_bucket="kyc-docs",
        storage_key="test/pan.pdf",
        content_type="application/pdf",
        size_bytes=1024,
        sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    )
    db_session.add(doc_version)
    db_session.commit()

    assert doc.id is not None
    assert doc_version.document_id == doc.id
    assert len(job.documents) == 1


def test_verification_result_creation(db_session):
    job = VerificationJob(status=JobStatus.COMPLETED)
    db_session.add(job)
    db_session.commit()

    res = VerificationResult(
        job_id=job.id,
        decision=VerificationDecision.VERIFIED,
        overall_score=0.95,
        name_match_score=0.98,
        dob_match_score=1.0,
        address_match_score=0.90,
        field_matches={"name": True, "dob": True},
        report_json={"verdict": "pass"},
    )
    db_session.add(res)
    db_session.commit()

    assert res.id is not None
    assert res.decision == VerificationDecision.VERIFIED
    assert res.overall_score == 0.95


def test_local_storage_client():
    storage = LocalStorageClient()
    bucket = "kyc-bucket"
    key = "documents/test.txt"
    data = b"Hello, KYC Document Verification!"

    sha = StorageClient.calculate_sha256(data)
    assert storage.verify_checksum(data, sha) is True

    stored_key = storage.put_object(bucket, key, data, "text/plain")
    assert stored_key == f"{bucket}/{key}"

    retrieved = storage.get_object(bucket, key)
    assert retrieved == data

    assert storage.delete_object(bucket, key) is True
    with pytest.raises(FileNotFoundError):
        storage.get_object(bucket, key)
