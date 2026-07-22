# Testing Strategy

## Current Test State

Verified during audit:

- `D:\Startrit_internship\.venv\Scripts\python.exe -m pytest tests -q`: 10 tests passed.
- Full `pytest -q` currently fails during collection due duplicate `ocr_test.py` module names.
- Source syntax compile outside virtualenv folders passed.
- Import checks show missing root-venv dependencies for face, Prefect, and Feast paths.

## Coverage Target

Minimum target: 85 percent meaningful coverage across maintained production code. Coverage should be measured per service and for the combined shared contract package.

## Test Layers

| Layer | Scope | Tools |
| --- | --- | --- |
| Unit tests | Pure matching logic, adapters, event schemas, storage clients, auth utilities | pytest, pytest-cov, pydantic validation |
| API tests | Gateway and service endpoints, auth, validation, error schemas | pytest, httpx AsyncClient, FastAPI TestClient |
| Integration tests | Postgres, Redis/RabbitMQ, MinIO, workers, event flow | pytest, testcontainers or docker compose test profile |
| Worker tests | OCR, face, verification workers with fake storage and fixture payloads | pytest, Celery eager mode or test queue |
| Database tests | Migrations, constraints, indexes, soft delete behavior | Alembic, pytest-postgresql, SQLAlchemy |
| Frontend tests | Components, forms, validation, query states, empty/error/loading states | Vitest, React Testing Library, axe |
| End-to-end tests | Upload, live status, result report, audit history | Playwright |
| Security tests | File validation, auth, RBAC, rate limits, secret scanning | bandit, pip-audit, gitleaks, OWASP ZAP baseline |

## Required Test Fixtures

- Valid PAN document image/PDF.
- Valid Aadhaar front/back image/PDF.
- Supporting document with matching name/address.
- Supporting document with name mismatch.
- Document with no extractable text.
- Document with unsupported MIME type.
- Oversized file.
- Face match pair.
- Face mismatch pair.
- No-face image/PDF.
- Corrupt PDF.

Fixtures must be synthetic or consent-cleared. Do not commit real KYC data.

## Service Test Plan

### API Gateway

- Login returns JWT and rejects invalid credentials.
- RBAC blocks unauthorized audit/settings access.
- Upload endpoints reject missing files, oversized files, unsupported MIME types, and invalid metadata.
- Upload creates job, document, document version, audit log, and `document.uploaded` event.
- OpenAPI schema validates.

### Document Service

- Stores bytes in MinIO/R2 adapter and metadata in PostgreSQL.
- Computes SHA-256 consistently.
- Deduplicates idempotent uploads.
- Soft delete hides documents but keeps audit log.

### OCR Service

- Consumes `document.uploaded`.
- Emits `ocr.started`, `ocr.completed`, or `ocr.failed`.
- Extracts PAN, Aadhaar, name, DOB, address, and raw text from fixtures.
- Handles Vertex/Gemini unavailable mode deterministically.
- Retries retryable failures and stops non-retryable failures.

### Face Verification Service

- Consumes applicable document events.
- Emits face lifecycle events.
- Detects face coordinates and stores face result.
- Handles no-face and low-confidence cases.
- Does not require public DB ids in API responses.

### Verification Service

- Computes name similarity, DOB match, address similarity, ID match, face score, and final score.
- Produces stable results for a stored `scoring_version`.
- Produces `review_required` for partial evidence.
- Generates report metadata and event.

### Notification/Status

- Persists every processing event.
- SSE endpoint replays events after `after_sequence`.
- Client reconnect does not duplicate terminal state.

## Frontend Test Plan

- Dashboard loads job counts and recent jobs.
- Upload KYC form validates required primary document.
- Supporting document upload supports multi-file flow.
- Status page updates from SSE without refresh.
- Results page renders score, evidence, and report download.
- Audit history supports empty, loading, error, and populated states.
- Settings page validates configurable limits.
- Dark mode and responsive breakpoints are covered by snapshots or Playwright screenshots.
- Accessibility checks pass for forms, nav, dialogs, and toasts.

## CI Gates

Every PR should run:

1. Python lint and formatting.
2. Python type check where practical.
3. Python unit/API tests with coverage.
4. Frontend lint, type check, and unit tests.
5. Docker build smoke test.
6. Security scans.
7. E2E smoke test against docker compose profile.

## Immediate Test Fixes

1. Add `pytest.ini` with `testpaths = tests`.
2. Rename manual scripts:
   - `3_kyc_verification/pan_aadhar_verification/ocr_test.py` to `ocr_api.py`.
   - `2_multi_agent_pipeline/.../agents/testing/ocr_test.py` to a unique test module or exclude it.
3. Add import smoke tests for every service entrypoint.
4. Add dependency lock validation in CI.
