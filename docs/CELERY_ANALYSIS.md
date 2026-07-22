# Celery Analysis

| Component | Source location | Purpose | Dependencies | Recommended source of truth | Migration strategy | Risk |
| --- | --- | --- | --- | --- | --- | --- |
| Celery app | `5_face_verification/face_verification_pipeline/app/celery_app.py` | Defines broker/backend and serialization | Celery, Redis | Yes | Keep single Celery app; extend task routes and queues here | Low |
| Face extraction task | `5_face_verification/face_verification_pipeline/app/tasks.py` | Renders PDF, extracts faces, stores `FaceRecord` rows | Celery, SQLModel, PyMuPDF, PIL, MTCNN/DeepFace via `face_analysis` | Yes | Route to `face_verification_queue`; expose via MCP | Medium |
| Face verification task | `tasks.py` | Re-crops reference face and runs trained verifier | Celery, SQLModel, PyMuPDF, DeepFace, joblib model | Yes | Route to `face_verification_queue`; expose via MCP | Medium |
| API dispatch | `5_face_verification/face_verification_pipeline/app/main.py` | Calls `extract_faces_task.delay` and `verify_faces_task.delay` | FastAPI, Celery | Yes | Keep API compatibility while LangGraph/MCP also dispatches tasks | Low |
| Compose worker | `5_face_verification/face_verification_pipeline/docker-compose.yml` | Runs single worker with Redis and Postgres | Docker, Redis, Postgres | Partial | Add queue-specific worker commands after queues are consolidated | Medium |

## Current Queues

The face service originally used Celery defaults. The architecture foundation added task routes for `face_verification_queue`. Required target queues are:

- `extraction_queue`
- `face_verification_queue`
- `validation_queue`
- `feature_store_queue`
- `inference_queue`
- `monitoring_queue`
- `performance_queue`

## Concurrency Gap

There is no current use of Celery groups, chords, or chains. The existing async LangGraph node already parallelizes document reading/extraction with `asyncio.gather`; the next Celery integration should use a group per independent document and a chord callback for validation.
