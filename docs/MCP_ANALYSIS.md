# MCP Analysis

## Finding

The repository has an `mcp` package, but `2_multi_agent_pipeline/credit_scoring_pipeline/mcp/mcp_server.py` is currently a LangGraph builder rather than a protocol-complete MCP server with registered tools. There is no discovered `FastMCP`, `@tool`, or tool discovery implementation in source files.

| Component | Source location | Purpose | Dependencies | Recommended source of truth | Migration strategy | Risk |
| --- | --- | --- | --- | --- | --- | --- |
| MCP package | `2_multi_agent_pipeline/credit_scoring_pipeline/mcp/__init__.py` | Package marker | None | Yes, package location | Keep package path; add real MCP server implementation beside graph code | Low |
| MCP graph module | `2_multi_agent_pipeline/credit_scoring_pipeline/mcp/mcp_server.py` | Builds LangGraph workflow | LangGraph, asyncio, Prefect tasks | Yes, for current workflow behavior | Rename responsibility internally or add tool registry while preserving `create_graph()` | Medium |

## Required Tools

| Tool | Backing implementation | Migration strategy | Risk |
| --- | --- | --- | --- |
| Document Classification Agent | `4_document_classification/Unified_extractor/unified_extractor.py` functions `determine_document_type`, `classify_by_content` | Expose as MCP tool after dependency boundaries are cleaned | Medium: Vertex fallback optional |
| Extraction Agent | `Unified_extractor.DocumentAgent.extract_data_with_gemini`; legacy `data_fetching_agent.DocumentAgent` | Expose Gemini extraction and regex fallback separately | High: external credentials and optional dependencies |
| Face Verification Agent | `5_face_verification/.../tasks.py`, `verify_faces.py`, `face_analysis.py` | MCP tool should dispatch existing Celery tasks | Medium: model file required |
| Validation Agent | `perform_verification_and_detect_anomalies`, PAN/Aadhaar regex validators | Extract validation into shared module, then expose | Medium |
| Feature Engineering Agent | `feature_engineering_agent_task` | Expose wrapper preserving `users` table contract | Low |
| Feature Store Agent | Feast repo contracts and repaired Feast writer | Expose only after `feast_writer_agent.py` missing import is fixed | High |
| Model Inference Agent | `1_model/mlruns` artifacts | Build MLflow loader around existing artifact | Medium |
| Monitoring Agent | `ai_platform/observability/tracing.py` plus OpenTelemetry later | Expose trace collection and health metrics | Medium |
| Performance Agent | `ai_platform/evaluation`, `ai_platform/benchmarks`, `doc_ext_pipeline/evaluate_model_df.py` | Expose benchmark/evaluation runners | Medium |

## Trace Requirement

Every MCP invocation should create an `AgentExecutionTrace`. Persisting traces requires a PostgreSQL table contract that is not currently present in the repo; add it only through an approved migration or an existing table owner.
