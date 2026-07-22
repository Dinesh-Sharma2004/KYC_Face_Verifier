# Entity Relationship Diagram

```mermaid
erDiagram
    users ||--o{ verification_jobs : creates
    users ||--o{ documents : uploads
    users ||--o{ audit_logs : acts

    verification_jobs ||--o{ documents : contains
    verification_jobs ||--o{ ocr_results : has
    verification_jobs ||--o{ face_results : has
    verification_jobs ||--|| verification_results : produces
    verification_jobs ||--o{ processing_events : emits
    verification_jobs ||--o{ audit_logs : audits

    documents ||--o{ document_versions : versions
    documents ||--o{ ocr_results : analyzed_by
    documents ||--o{ face_results : used_by
    documents ||--o{ processing_events : updates
    documents ||--o{ audit_logs : audits

    document_versions ||--o{ ocr_results : source

    users {
        uuid id PK
        text email UK
        text full_name
        text role
        uuid tenant_id
        text password_hash
        boolean is_active
        timestamptz created_at
        timestamptz updated_at
        timestamptz deleted_at
    }

    verification_jobs {
        uuid id PK
        uuid tenant_id
        uuid user_id FK
        text external_reference
        job_status status
        text status_reason
        uuid trace_id
        text idempotency_key UK
        timestamptz queued_at
        timestamptz started_at
        timestamptz completed_at
        timestamptz failed_at
        timestamptz deleted_at
    }

    documents {
        uuid id PK
        uuid job_id FK
        uuid tenant_id
        uuid uploaded_by FK
        document_role role
        text document_type_hint
        text detected_document_type
        text original_filename
        text content_type
        bigint size_bytes
        text sha256
        integer current_version
        jsonb metadata
        timestamptz deleted_at
    }

    document_versions {
        uuid id PK
        uuid document_id FK
        integer version
        text storage_provider
        text storage_bucket
        text storage_key UK
        text content_type
        bigint size_bytes
        text sha256
        boolean is_current
        timestamptz deleted_at
    }

    ocr_results {
        uuid id PK
        uuid job_id FK
        uuid document_id FK
        uuid document_version_id FK
        text status
        text engine
        text detected_document_type
        numeric classification_confidence
        text raw_text_storage_key
        jsonb extracted_entities
        jsonb validation_errors
        timestamptz deleted_at
    }

    face_results {
        uuid id PK
        uuid job_id FK
        uuid document_id FK
        uuid reference_document_id FK
        uuid probe_document_id FK
        text status
        integer faces_detected
        boolean match
        numeric confidence
        text model_version
        jsonb bounding_boxes
        timestamptz deleted_at
    }

    verification_results {
        uuid id PK
        uuid job_id FK
        verification_decision decision
        numeric score
        numeric threshold
        text scoring_version
        jsonb checks
        jsonb matched_entities
        text report_storage_key
        text report_sha256
        timestamptz deleted_at
    }

    audit_logs {
        uuid id PK
        uuid tenant_id
        uuid actor_user_id FK
        uuid job_id FK
        uuid document_id FK
        text action
        text resource_type
        uuid resource_id
        inet ip_address
        jsonb details
        timestamptz created_at
    }

    processing_events {
        uuid id PK
        uuid event_id UK
        uuid job_id FK
        uuid document_id FK
        bigint sequence
        text event_type
        integer event_version
        job_status status
        text producer
        uuid trace_id
        text idempotency_key
        jsonb payload
        timestamptz occurred_at
    }
```

## Notes

- `documents` store metadata only; bytes live in MinIO locally or Cloudflare R2 in production.
- `document_versions` enables re-upload, preprocessed variants, and immutable object pointers.
- `processing_events` supports real-time SSE/WebSocket replay and auditability.
- Soft deletes are included on user-facing mutable tables. Audit logs are append-only.
