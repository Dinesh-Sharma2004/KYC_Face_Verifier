CREATE EXTENSION IF NOT EXISTS pgcrypto;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'document_role') THEN
        CREATE TYPE document_role AS ENUM ('primary', 'supporting');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'job_status') THEN
        CREATE TYPE job_status AS ENUM (
            'queued',
            'processing',
            'ocr_running',
            'face_verification',
            'matching',
            'completed',
            'failed',
            'cancelled'
        );
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'verification_decision') THEN
        CREATE TYPE verification_decision AS ENUM ('verified', 'review_required', 'rejected', 'failed');
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS users (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    email text UNIQUE,
    full_name text,
    role text NOT NULL DEFAULT 'analyst',
    tenant_id uuid,
    password_hash text,
    is_active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    deleted_at timestamptz
);

CREATE TABLE IF NOT EXISTS verification_jobs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid,
    user_id uuid REFERENCES users(id),
    external_reference text,
    status job_status NOT NULL DEFAULT 'queued',
    status_reason text,
    trace_id uuid NOT NULL DEFAULT gen_random_uuid(),
    idempotency_key text UNIQUE,
    queued_at timestamptz NOT NULL DEFAULT now(),
    started_at timestamptz,
    completed_at timestamptz,
    failed_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    deleted_at timestamptz
);

CREATE TABLE IF NOT EXISTS documents (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id uuid NOT NULL REFERENCES verification_jobs(id),
    tenant_id uuid,
    uploaded_by uuid REFERENCES users(id),
    role document_role NOT NULL,
    document_type_hint text,
    detected_document_type text,
    original_filename text NOT NULL,
    content_type text NOT NULL,
    size_bytes bigint NOT NULL CHECK (size_bytes >= 0),
    sha256 text NOT NULL,
    current_version integer NOT NULL DEFAULT 1,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    deleted_at timestamptz,
    UNIQUE (job_id, sha256)
);

CREATE TABLE IF NOT EXISTS document_versions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id uuid NOT NULL REFERENCES documents(id),
    version integer NOT NULL,
    storage_provider text NOT NULL,
    storage_bucket text NOT NULL,
    storage_key text NOT NULL,
    content_type text NOT NULL,
    size_bytes bigint NOT NULL CHECK (size_bytes >= 0),
    sha256 text NOT NULL,
    is_current boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    deleted_at timestamptz,
    UNIQUE (document_id, version),
    UNIQUE (storage_provider, storage_bucket, storage_key)
);

CREATE TABLE IF NOT EXISTS ocr_results (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id uuid NOT NULL REFERENCES verification_jobs(id),
    document_id uuid NOT NULL REFERENCES documents(id),
    document_version_id uuid REFERENCES document_versions(id),
    status text NOT NULL,
    engine text NOT NULL,
    engine_version text,
    detected_document_type text,
    classification_confidence numeric(5,4),
    raw_text text,
    raw_text_storage_key text,
    extracted_entities jsonb NOT NULL DEFAULT '{}'::jsonb,
    validation_errors jsonb NOT NULL DEFAULT '[]'::jsonb,
    started_at timestamptz,
    completed_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    deleted_at timestamptz
);

CREATE TABLE IF NOT EXISTS face_results (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id uuid NOT NULL REFERENCES verification_jobs(id),
    document_id uuid REFERENCES documents(id),
    reference_document_id uuid REFERENCES documents(id),
    probe_document_id uuid REFERENCES documents(id),
    status text NOT NULL,
    faces_detected integer NOT NULL DEFAULT 0 CHECK (faces_detected >= 0),
    reference_face_storage_key text,
    probe_face_storage_key text,
    bounding_boxes jsonb NOT NULL DEFAULT '[]'::jsonb,
    match boolean,
    confidence numeric(5,4),
    model_name text,
    model_version text,
    error_code text,
    error_message text,
    started_at timestamptz,
    completed_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    deleted_at timestamptz
);

CREATE TABLE IF NOT EXISTS verification_results (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id uuid NOT NULL UNIQUE REFERENCES verification_jobs(id),
    decision verification_decision NOT NULL,
    score numeric(5,2) NOT NULL CHECK (score >= 0 AND score <= 100),
    threshold numeric(5,2) NOT NULL DEFAULT 80,
    scoring_version text NOT NULL,
    checks jsonb NOT NULL DEFAULT '{}'::jsonb,
    matched_entities jsonb NOT NULL DEFAULT '{}'::jsonb,
    report_storage_bucket text,
    report_storage_key text,
    report_sha256 text,
    generated_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    deleted_at timestamptz
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid,
    actor_user_id uuid REFERENCES users(id),
    job_id uuid REFERENCES verification_jobs(id),
    document_id uuid REFERENCES documents(id),
    action text NOT NULL,
    resource_type text NOT NULL,
    resource_id uuid,
    ip_address inet,
    user_agent text,
    details jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS processing_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id uuid NOT NULL UNIQUE,
    job_id uuid NOT NULL REFERENCES verification_jobs(id),
    document_id uuid REFERENCES documents(id),
    sequence bigint GENERATED BY DEFAULT AS IDENTITY,
    event_type text NOT NULL,
    event_version integer NOT NULL DEFAULT 1,
    status job_status,
    producer text NOT NULL,
    trace_id uuid NOT NULL,
    idempotency_key text NOT NULL,
    payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    error_code text,
    error_message text,
    occurred_at timestamptz NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (job_id, idempotency_key)
);

CREATE INDEX IF NOT EXISTS idx_users_tenant_active ON users (tenant_id, is_active) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_jobs_tenant_status ON verification_jobs (tenant_id, status) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_jobs_user_created ON verification_jobs (user_id, created_at DESC) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_documents_job_role ON documents (job_id, role) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_documents_sha256 ON documents (sha256);
CREATE INDEX IF NOT EXISTS idx_document_versions_document ON document_versions (document_id, version DESC) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_ocr_results_job_document ON ocr_results (job_id, document_id) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_face_results_job ON face_results (job_id) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_verification_results_decision ON verification_results (decision, created_at DESC) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_audit_logs_job_created ON audit_logs (job_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_processing_events_job_sequence ON processing_events (job_id, sequence);
CREATE INDEX IF NOT EXISTS idx_processing_events_type_created ON processing_events (event_type, created_at DESC);
