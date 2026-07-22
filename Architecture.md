# KYC Document Verification Platform Architecture

## Audit Summary

This repository currently contains several useful but disconnected implementations: a Streamlit operator console, a FastAPI unified extractor, a legacy Flask PAN/Aadhaar OCR API, a FastAPI/Celery face service, Prefect/LangGraph orchestration experiments, and shared `ai_platform` contract scaffolding. It does not yet contain the requested React/Vite/Tailwind frontend, API gateway, single durable job model, object-storage abstraction, database migrations, real-time status stream, or complete Docker environment.

The target system should be built incrementally from the existing strongest modules, with the current extractors and face worker wrapped behind stable service contracts before any broad rewrite.

## Current Architecture

```mermaid
flowchart LR
    Operator[Operator] --> Streamlit[ai_platform/frontend/streamlit_app.py]
    Streamlit --> Unified[Unified Extractor FastAPI<br/>4_document_classification/Unified_extractor]
    Streamlit --> Legacy[Legacy PAN/Aadhaar Flask API<br/>3_kyc_verification]
    Streamlit --> Ledger[Local JSON Ledger<br/>ai_platform/frontend/data]

    Unified --> Tesseract[Tesseract OCR optional]
    Unified --> Vertex[Vertex/Gemini optional]
    Unified --> Memory[In-request aggregation]

    Legacy --> Vertex2[Vertex AI OCR optional]
    Legacy --> Regex[Regex KYC extraction]

    FaceAPI[Face FastAPI<br/>5_face_verification] --> Redis[Redis/Celery broker]
    Redis --> FaceWorker[Celery worker]
    FaceWorker --> FaceDB[(Postgres face_db)]
    FaceWorker --> LocalPDF[Local PDF volume]

    Prefect[Prefect flow] --> LangGraph[LangGraph/MCP graph]
    LangGraph --> DataAgent[Data fetching agent]
    LangGraph --> FeatureAgent[Feature engineering agent]
    FeatureAgent --> CreditDB[(credit_db or SQLite fallback)]
```

## Current Data Flow

```mermaid
sequenceDiagram
    participant U as Operator
    participant S as Streamlit Console
    participant E as Unified/Legacy Extractor
    participant L as Local Ledger
    participant F as Face API
    participant C as Celery Worker
    participant D as Service-local Postgres

    U->>S: Upload client and KYC documents
    S->>S: Store uploaded bytes under local uploads
    S->>E: POST files synchronously
    E->>E: OCR, classify, extract, aggregate
    E-->>S: Extraction payload
    S->>S: Build simple verification summary
    S->>L: Write JSON job/customer ledger
    U->>F: Optional face extraction call
    F->>D: Insert Document row
    F->>C: Queue Celery task
    C->>D: Insert FaceRecord rows
    U->>F: Poll task status
```

## Current Service Dependency Diagram

```mermaid
flowchart TD
    Streamlit --> Requests[requests]
    Streamlit --> LocalFiles[local filesystem]
    UnifiedExtractor --> FastAPI
    UnifiedExtractor --> Pydantic
    UnifiedExtractor --> Pillow
    UnifiedExtractor --> PDF2Image
    UnifiedExtractor --> Tesseract
    UnifiedExtractor --> VertexAI
    LegacyOCR --> Flask
    LegacyOCR --> GoogleVision
    LegacyOCR --> OpenCV
    FaceService --> FastAPI
    FaceService --> SQLModel
    FaceService --> Postgres
    FaceService --> Redis
    FaceService --> Celery
    FaceService --> DeepFace
    FaceService --> PyMuPDF
    FaceService --> LocalDisk
    PrefectFlow --> Prefect
    PrefectFlow --> LangGraph
    PrefectFlow --> Feast
    PrefectFlow --> SQLAlchemy
```

## Desired Architecture

The desired platform should expose one external API gateway and route work to domain services through events and queues. Services may begin as modules in one repository, but their boundaries should be explicit so they can later be deployed independently.

```mermaid
flowchart LR
    UI[React/Vite Enterprise Dashboard] --> Gateway[API Gateway]
    Gateway --> Auth[JWT/RBAC]
    Gateway --> DocumentService[Document Service]
    Gateway --> VerificationService[Verification Service]
    Gateway --> StatusStream[SSE/WebSocket Status Stream]

    DocumentService --> ObjectStore[(MinIO local / Cloudflare R2 prod)]
    DocumentService --> DB[(PostgreSQL)]
    DocumentService --> EventBus[(Redis Streams or RabbitMQ)]

    EventBus --> OCRService[OCR Service Workers]
    EventBus --> FaceService[Face Verification Workers]
    EventBus --> VerificationService
    EventBus --> NotificationService[Notification Service]
    EventBus --> AuditService[Audit Service]

    OCRService --> DB
    FaceService --> DB
    VerificationService --> DB
    AuditService --> DB

    Metrics[Prometheus] --> Grafana[Grafana]
    Gateway --> Metrics
    OCRService --> Metrics
    FaceService --> Metrics
    VerificationService --> Metrics
```

## Desired Backend Boundaries

| Service | Responsibilities | Current source to wrap | Target persistence |
| --- | --- | --- | --- |
| API Gateway | Auth, routing, upload coordination, OpenAPI, rate limiting, status stream | New FastAPI service using `ai_platform.contracts` | PostgreSQL sessions and job reads |
| Document Service | Upload validation, metadata, versioning, object storage | New service; reuse `kyc_gateway.document_hash` | `documents`, `document_versions` |
| OCR Service | OCR and entity extraction | `4_document_classification/Unified_extractor`, legacy PAN/Aadhaar regex | `ocr_results`, events |
| Face Verification Service | Face extraction and comparison | `5_face_verification/face_verification_pipeline` | `face_results`, events |
| Verification Service | Name/DOB/address/ID/entity matching, scoring, report generation | `build_verification_summary`, unified schemas | `verification_results` |
| Notification Service | Status fan-out to SSE/WebSocket and optional email/webhook | New | `processing_events` |
| Audit Service | Immutable audit logs and security events | New | `audit_logs` |

## Desired Queue Flow

```mermaid
flowchart TD
    Upload[document.uploaded] --> OCRStart[ocr.started]
    OCRStart --> OCRDone[ocr.completed]
    OCRStart --> OCRFailed[ocr.failed]
    Upload --> FaceMaybe{Face applicable?}
    FaceMaybe --> FaceStart[face.started]
    FaceStart --> FaceDone[face.completed]
    FaceStart --> FaceFailed[face.failed]
    OCRDone --> VerifyStart[verification.started]
    FaceDone --> VerifyStart
    OCRFailed --> VerifyStart
    FaceFailed --> VerifyStart
    VerifyStart --> VerifyDone[verification.completed]
    VerifyStart --> VerifyFailed[verification.failed]
    VerifyDone --> Report[report.generated]
```

## Frontend Target

The requested frontend does not exist in the current workspace. The target should be a new React/Vite/TypeScript app with Tailwind, shadcn/ui, TanStack Query, React Hook Form, Zod, dark mode, error boundaries, skeletons, toasts, and accessible responsive layouts.

Required pages:

- Dashboard
- Upload KYC
- Upload Supporting Documents
- Verification Status
- Verification Results
- Audit History
- Settings

## Database Target

Use one PostgreSQL schema with UUID primary keys, foreign keys, soft deletes, status/event history, and indexes for user, job, document, event, and result lookups. `schema.sql` is the proposed migration baseline.

## Storage Target

Documents must be stored outside PostgreSQL. The application should use a storage interface with these implementations:

- Local development: MinIO using S3-compatible API.
- Production: Cloudflare R2 using S3-compatible API.

PostgreSQL stores metadata, object keys, checksums, content type, size, version, and retention flags only.

## Observability Target

Every service should emit structured JSON logs with `trace_id`, `job_id`, `document_id`, `service`, `event_type`, `duration_ms`, and `status`. Prometheus should scrape service health/metrics. OpenTelemetry traces should connect gateway requests to queue jobs and worker execution.

## Architecture Risks

- Current code mixes synchronous request processing with long-running OCR/LLM work.
- There is no authoritative job state machine.
- Current queues are only partially used by the face service.
- Local disk storage prevents reliable cloud deployment.
- Current frontend is Streamlit, not the requested React enterprise dashboard.
- Secrets and generated data are present in the repository.
- Dependency sets are unpinned or conflicting.
- Docker Compose is fragmented and incomplete.
