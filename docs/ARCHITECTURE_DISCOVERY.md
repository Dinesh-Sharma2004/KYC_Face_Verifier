# Architecture Discovery

This repository is not greenfield. The current strongest implementations are:

| Area | Current source of truth | Notes |
| --- | --- | --- |
| LangGraph orchestration | `2_multi_agent_pipeline/credit_scoring_pipeline/mcp/mcp_server.py` | Most useful graph shape today: async fan-out over documents, then feature engineering. |
| MCP | `2_multi_agent_pipeline/credit_scoring_pipeline/mcp/mcp_server.py` | MCP is present but currently mixed with graph construction and not exposed as a stable tool catalog. |
| Prefect | `2_multi_agent_pipeline/credit_scoring_pipeline/main_graph.py` and `flows/` | Existing tasks should remain wrappers around agent nodes where useful. |
| Feast | `2_multi_agent_pipeline/credit_scoring_pipeline/features/feature_repo` | Existing `applicant_id` entity and `credit_score_features` view should be reused. |
| Document schemas | `4_document_classification/Unified_extractor/schemas.py` | Richest Pydantic schema set, including Karnataka property documents. |
| Document extraction | `4_document_classification/Unified_extractor/unified_extractor.py` | Best classification/extraction implementation with OCR-first and Vertex/Gemini fallback. |
| Legacy KYC extraction | `2_multi_agent_pipeline/credit_scoring_pipeline/agents/data_fetching_agent.py` and `3_kyc_verification` | Useful PAN/Aadhaar regex and OCR logic; should become shared validation/extraction helpers. |
| Face service schema | `5_face_verification/face_verification_pipeline/app/models.py` | Existing SQLModel `Document` and `FaceRecord` tables must not be redesigned. |
| Face queue execution | `5_face_verification/face_verification_pipeline/app/tasks.py` | Existing Celery implementation does long-running face extraction/verification. |
| Advanced face processing | `doc_ext_pipeline` | Best experiments for MTCNN/DeepFace preprocessing and batch evaluation. |
| Model artifacts | `1_model/mlruns` | MLflow artifacts are present; inference agent should load via MLflow/model registry path, not copy model code. |

## Duplicates To Consolidate

- Document schemas exist in both `4_document_classification/Unified_extractor/schemas.py` and `2_multi_agent_pipeline/credit_scoring_pipeline/agents/utils/schemas.py`.
- Face detection/verification exists in `5_face_verification` and `doc_ext_pipeline`.
- Database access is service-local in feature engineering and face verification.
- Docker Compose exists per service, but not for the complete platform.
- Evaluation utilities exist in `doc_ext_pipeline`, but not as a cross-agent framework.

## Schema Contract

Do not redesign existing tables. Current table owners:

- Face verification: `Document`, `FaceRecord` in `5_face_verification/face_verification_pipeline/app/models.py`.
- Feature engineering: `users` table defined in `2_multi_agent_pipeline/credit_scoring_pipeline/agents/feature_engineering_agent.py`.
- Feast source: `credit_score_data` queried by `credit_score_features`.

The new `ai_platform.contracts` package adds cross-service payload contracts only. It does not create or mutate database tables.

## Target Graph

`Intake Agent -> LangGraph -> parallel document classification/extraction/face tasks -> validation -> feature engineering -> Feast sync -> MLflow inference -> monitoring/performance reporting`

Celery runs long tasks on dedicated queues; LangGraph remains the workflow decision layer.
