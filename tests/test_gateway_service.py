"""Integration & E2E API tests for FastAPI Gateway, document upload, processing pipeline, and verification results."""

import os

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("KYC_JOB_TOKEN_SECRET", "test-job-token-secret")
os.environ.setdefault("KYC_ADMIN_API_TOKEN", "test-admin-token")
os.environ.setdefault("KYC_ADMIN_PASSWORD", "unit-test-admin-passphrase")

from ai_platform.db.session import init_db
from ai_platform.services.gateway import app


@pytest.fixture
def client():
    init_db()
    return TestClient(app)


def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "kyc-gateway"


def test_login(client):
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "analyst@example.com", "password": os.environ["KYC_ADMIN_PASSWORD"]},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["role"] == "analyst"


def test_full_kyc_verification_flow(client):
    # 1. Create Job
    res_job = client.post("/api/v1/jobs", json={"external_reference": "REF-1001"})
    assert res_job.status_code == 201
    job_data = res_job.json()
    job_id = job_data["job_id"]
    assert job_data["status"] == "queued"

    # 2. Upload Primary KYC Document (PAN Card sample)
    pan_bytes = b"GOVERNMENT OF INDIA\nINCOME TAX DEPARTMENT\nPERMANENT ACCOUNT NUMBER: ABCDE1234F\nNAME: JANE DOE\nDOB: 12/04/1992"
    res_doc1 = client.post(
        f"/api/v1/jobs/{job_id}/documents",
        data={"role": "primary", "document_type_hint": "PAN_CARD"},
        files={"file": ("pan_card.jpg", pan_bytes, "image/jpeg")},
    )
    assert res_doc1.status_code == 200
    doc1_data = res_doc1.json()
    assert doc1_data["role"] == "primary"

    # 3. Upload Supporting Document (Aadhaar Card sample)
    aadhaar_bytes = b"GOVERNMENT OF INDIA\nAADHAAR\n1234 5678 9012\nNAME: JANE DOE\nDOB: 12/04/1992\nAddress: 123 Main Street"
    res_doc2 = client.post(
        f"/api/v1/jobs/{job_id}/documents",
        data={"role": "supporting", "document_type_hint": "AADHAAR_CARD"},
        files={"file": ("aadhaar_card.jpg", aadhaar_bytes, "image/jpeg")},
    )
    assert res_doc2.status_code == 200
    assert res_doc2.json()["role"] == "supporting"

    # 4. Trigger Processing Pipeline
    res_proc = client.post(f"/api/v1/jobs/{job_id}/process")
    assert res_proc.status_code == 200
    assert res_proc.json()["status"] == "processing_started"

    # 5. Poll Job status until completion
    status_res = client.get(f"/api/v1/jobs/{job_id}")
    assert status_res.status_code == 200
    job_status = status_res.json()["status"]
    assert job_status in ["completed", "processing", "ocr_running", "face_verification", "matching"]

    # 6. Fetch Verification Result
    res_result = client.get(f"/api/v1/jobs/{job_id}/result")
    assert res_result.status_code == 200
    result_data = res_result.json()
    assert result_data["decision"] in ["verified", "review_required", "rejected"]
    assert result_data["overall_score"] > 0.0
    assert "field_scores" in result_data

    # 7. Fetch Audit Logs
    audit_res = client.get("/api/v1/audit/logs", headers={"Authorization": "Bearer test-admin-token"})
    assert audit_res.status_code == 200
    logs = audit_res.json()
    assert len(logs) > 0
