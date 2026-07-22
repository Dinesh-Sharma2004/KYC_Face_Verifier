# Refactoring Plan

## Phase 1: Stabilize Contracts

- Use `ai_platform.contracts.schemas` for cross-service payloads.
- Reuse `4_document_classification/Unified_extractor/schemas.py` as the detailed document schema source.
- Keep existing PostgreSQL and Feast definitions unchanged.
- Add queue routing constants in `ai_platform.contracts.queues`.

## Phase 2: Preserve And Wrap Existing Implementations

- Wrap `Unified_extractor` classification and extraction as Document Classification and Extraction agents.
- Wrap `5_face_verification` Celery tasks as Face Verification Agent execution.
- Wrap existing feature engineering and Feast writer logic as Feature Engineering and Feature Store agents.
- Keep MCP as the tool interoperability layer and expose these wrappers as tools.

## Phase 3: Production Orchestration

- Extend the existing LangGraph graph to maintain `WorkflowState`.
- Use parallel document branches for independent PAN, Aadhaar, bank statement, and land record processing.
- Dispatch heavy steps to Celery queues, then rejoin in LangGraph for validation and final decisions.

## Phase 4: Observability And Evaluation

- Emit one `AgentExecutionTrace` per agent execution.
- Persist traces through the owning platform database layer once the existing schema authority is selected.
- Add Langfuse/OpenTelemetry exporters around agent and workflow calls.
- Use `ai_platform.evaluation.metrics` for extraction, face verification, validation, and orchestrator reports.

## Phase 5: Benchmarking

- Implement the benchmark suites in `ai_platform.benchmarks.suites`.
- Generate reports for latency, throughput, queue wait time, worker utilization, failure rate, and recovery rate.

## First Implementation Slice Completed

- Added shared platform package with schemas, queue routes, trace recorder, evaluation metrics, and benchmark suite definitions.
- Added architecture discovery and migration plan documentation.
- Updated the face Celery app to route existing face tasks to `face_verification_queue`.
