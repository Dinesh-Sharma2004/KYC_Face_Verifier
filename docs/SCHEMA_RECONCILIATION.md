# Schema Reconciliation

## Summary

The repository has four schema families. The source of truth for detailed document extraction is `4_document_classification/Unified_extractor/schemas.py`. The source of truth for persisted face records is `5_face_verification/face_verification_pipeline/app/models.py`. The source of truth for feature engineering persistence is the `users` table declared in `2_multi_agent_pipeline/credit_scoring_pipeline/agents/feature_engineering_agent.py`. Feast contracts remain in `2_multi_agent_pipeline/credit_scoring_pipeline/features/feature_repo`.

## Components

| Component | Source location | Purpose | Dependencies | Recommended source of truth | Migration strategy | Risk |
| --- | --- | --- | --- | --- | --- | --- |
| Rich document schemas | `4_document_classification/Unified_extractor/schemas.py` | Pydantic schemas for tax invoice, bank statement, salary slip, Aadhaar, PAN, sale deed, and Karnataka property docs | Pydantic, `datetime.date` | Yes, for document payload shape | Import or adapt to `ai_platform/schema/unified_schema.py`; preserve enum values and field names | Medium: some required Karnataka fields can reject partial extraction |
| Legacy agent document schemas | `2_multi_agent_pipeline/credit_scoring_pipeline/agents/utils/schemas.py` | Minimal PAN/Aadhaar schemas used by data fetching and feature engineering | Pydantic | No | Convert through adapters into unified identity document payloads | Medium: date and nested Aadhaar shape differ |
| Legacy Flask KYC schemas | `3_kyc_verification/pan_aadhar_verification/ocr_test.py` | Aadhaar front/back and PAN models embedded in Flask OCR service | Flask, Pydantic, Vertex AI | No | Keep as input compatibility adapter; migrate OCR logic later | High: service embeds config and schemas in one file |
| Face database models | `5_face_verification/face_verification_pipeline/app/models.py` | SQLModel `Document` and `FaceRecord` persisted in PostgreSQL | SQLModel | Yes, for face DB schema | Mirror field names in unified schema; do not mutate table definitions | Low: compact and clear |
| Feature engineering table | `2_multi_agent_pipeline/credit_scoring_pipeline/agents/feature_engineering_agent.py` | SQLAlchemy `users` table with identity verification fields | SQLAlchemy, PostgreSQL/SQLite fallback | Yes, for engineered identity table | Mirror table fields in unified schema; keep fallback behavior | Medium: table is created dynamically in agent code |
| Feast feature schema | `2_multi_agent_pipeline/credit_scoring_pipeline/features/feature_repo/feature_view.py` | `credit_score_features` view over `credit_score_data` | Feast, PostgreSQLSource | Yes, for model feature contract | Mirror fields only; no Feast redesign | Low |
| Draft platform contracts | `ai_platform/contracts/schemas.py` | Cross-service job, document, trace, and workflow payloads | Pydantic | Yes, for orchestration payloads only | Keep separate from DB table contracts; map DB records explicitly | Low |

## Overlaps And Conflicts

| Concept | Existing variants | Conflict | Resolution |
| --- | --- | --- | --- |
| Document type | `DocumentType` enum uses uppercase values; legacy agents use `"PAN Card"` / `"Aadhaar Card"` | Case and spacing differ | Unified schema stores uppercase enum and adapter normalizes legacy strings |
| Aadhaar name | `full_name_en`, `full_name_native`, `full_name` | Legacy minimal schema uses `full_name`; rich schema separates language | Preserve all fields; map `full_name` to `full_name_native` only when no language-specific value exists |
| Aadhaar DOB | `date_of_birth: str`, `date`, or nested front data | Type and nesting differ | Unified schema accepts optional string to preserve raw extraction; feature adapter may parse dates where needed |
| Aadhaar address | Back data has `address`; feature table has `aadhaar_address` | Same concept with table-specific name | Adapter maps extracted address to persisted `aadhaar_address` |
| PAN name | `full_name_en`, `full_name`, `father_name` | Minimal schema references `full_name`, rich schema uses `full_name_en` | Preserve `full_name_en`; adapter falls back to `full_name` |
| Face bbox | Existing DB stores `bbox_left`, `bbox_top`, `bbox_width`, `bbox_height`; extraction functions return list `[x, y, w, h]` or `[x1, y1, x2, y2]` | Different coordinate conventions | Unified persisted contract follows DB fields; adapters require caller to specify format |
| Verification confidence | Face DB uses `verification_confidence`; DeepFace wrapper returns `probability` | Name mismatch | Adapter maps `probability` to `verification_confidence` |

## PostgreSQL Contracts

| Table | Source | Fields | Notes |
| --- | --- | --- | --- |
| `document` / SQLModel default | `5_face_verification/.../models.py` | `id`, `url`, `filename`, `file_path`, `created_at` | Table name is SQLModel-derived from `Document`; do not rename |
| `facerecord` / SQLModel default | `5_face_verification/.../models.py` | `id`, `face_id`, `document_id`, page/bbox/confidence/status/analysis/verification fields | Bbox units depend on rendered DPI scaling in Celery task |
| `users` | `feature_engineering_agent.py` | `user_name`, `date_of_birth`, `age`, Aadhaar/PAN verification fields, timestamps | Primary key is `user_name`; PostgreSQL upsert uses conflict on `user_name` |
| `user_credit_documents` | `feast_writer_agent.py` | `id`, `file`, `chunk_id`, `text`, `schema_json`, `timestamp` | Agent references missing `agents.utils.schema.CreditScoreDataSchema`; needs repair before use |
| `credit_score_data` | `feature_view.py` | `applicant_id`, `age`, `income`, `credit_history_length`, `number_of_loans`, `loan_amount`, `default_history`, `submission_date` | Feast source query contract |

## Recommended Unified Schema

Create `ai_platform/schema/unified_schema.py` with explicit contracts for:

- document extraction payloads
- face DB row mirrors
- feature engineering `users` table rows
- Feast `credit_score_data` rows
- agent trace rows

The schema must not create tables or change Feast. It is a contract and adapter layer only.
