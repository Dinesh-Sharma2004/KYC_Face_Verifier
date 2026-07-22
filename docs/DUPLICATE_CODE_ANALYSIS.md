# Duplicate Code Analysis

| Area | Source locations | Purpose | Recommended source of truth | Migration strategy | Risk |
| --- | --- | --- | --- | --- | --- |
| PAN/Aadhaar schemas | `4_document_classification/Unified_extractor/schemas.py`, `2_multi_agent_pipeline/.../agents/utils/schemas.py`, `3_kyc_verification/.../ocr_test.py` | Validate extracted identity fields | `4_document_classification/Unified_extractor/schemas.py` for extraction; `ai_platform/schema/unified_schema.py` for platform contracts | Add adapters from legacy minimal/Flask outputs to unified schema | Medium |
| Regex extraction | `data_fetching_agent.py`, `3_kyc_verification/.../ocr_test.py` | PAN, Aadhaar, DOB, gender, names, addresses | `data_fetching_agent.py` for current async agent; Flask version has extra guardian/YOB logic | Move to `ai_platform/shared/validation` after tests prove parity | Medium |
| OCR | `data_fetching_agent.py` uses Google Vision; `Unified_extractor` uses Tesseract preview plus Vertex/Gemini; Flask legacy uses Vertex vision prompt | Multiple OCR/extraction strategies | `Unified_extractor` for classification/extraction; Google Vision path as fallback | Wrap both behind one extraction agent; keep optional dependency checks | High |
| Document preprocessing | `Unified_extractor.downscale_image_bytes`, PDF conversion; `data_fetching_agent` PDF text/OCR; `utils/pdf_doc_parser.py` LangChain split | Image/PDF preparation | `Unified_extractor` for extraction preprocessing | Move stable image/PDF conversion helpers into shared module later | Medium |
| Face detection | `5_face_verification/app/face_analysis.py`, `doc_ext_pipeline/main.py`, `doc_ext_pipeline/preprocessor.py`, `data_fetching_agent.ImageProcessor._face_detect` | Detect faces in documents/images | `5_face_verification/app/face_analysis.py` for service DB path; `doc_ext_pipeline` for benchmark/evaluation improvements | Merge MTCNN/DeepFace improvements into face service after regression tests | High |
| Face verification | `5_face_verification/app/verify_faces.py`, `doc_ext_pipeline/main.py` direct `DeepFace.verify` | Compare identity images | `5_face_verification/app/verify_faces.py` | Keep trained multi-model verifier; use direct DeepFace verify only for diagnostics | Medium |
| Feature writing | `feature_engineering_agent.py`, `feast_writer_agent.py`, Feast repo files | DB upsert and Feast ingestion | Feature engineering `users` table and Feast `credit_score_features` | Repair or retire dynamic `doc_chunks_view` writer | High |
| Orchestration | `main_graph.py`, `mcp/mcp_server.py`, `flows/orchestrator.py`, `ai_platform/orchestration/graph.py` | Workflow coordination | Existing async `mcp/mcp_server.py` plus Prefect flow | Refactor existing graph nodes to MCP tools before adopting shared graph | Medium |

## Removal Policy

Do not delete original implementations until:

1. A unified adapter test covers the old output shape.
2. The new shared implementation is invoked by at least one service.
3. Existing service tests or smoke tests pass.
