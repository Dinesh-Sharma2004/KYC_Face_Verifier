"""Production-oriented LangGraph skeleton for the multi-agent workflow."""

from typing import Any, Callable, Dict

from ai_platform.contracts.schemas import AgentStatus, WorkflowState
from ai_platform.observability.tracing import AgentTraceRecorder

AgentHandler = Callable[[WorkflowState], WorkflowState]


def _default_handler(agent_name: str) -> AgentHandler:
    def handler(state: WorkflowState) -> WorkflowState:
        recorder = AgentTraceRecorder(state.job.trace_id, state.job.job_id)
        with recorder.trace(agent_name) as trace:
            state.traces.append(trace)
        return state

    return handler


def build_platform_graph(agent_handlers: Dict[str, AgentHandler] | None = None) -> Any:
    """Build the platform LangGraph without moving decisions into Celery.

    Handlers may synchronously submit Celery tasks and wait/poll for task IDs, but
    routing, validation, failure handling, and final workflow state stay here.
    """

    from langgraph.graph import END, StateGraph

    handlers = agent_handlers or {}

    def run_agent(agent_name: str) -> AgentHandler:
        return handlers.get(agent_name, _default_handler(agent_name))

    def intake(state: WorkflowState) -> WorkflowState:
        state.job.status = AgentStatus.RUNNING
        return run_agent("intake_agent")(state)

    def classify(state: WorkflowState) -> WorkflowState:
        return run_agent("document_classification_agent")(state)

    def extract(state: WorkflowState) -> WorkflowState:
        return run_agent("extraction_agent")(state)

    def face_verify(state: WorkflowState) -> WorkflowState:
        return run_agent("face_verification_agent")(state)

    def validate(state: WorkflowState) -> WorkflowState:
        return run_agent("validation_agent")(state)

    def engineer_features(state: WorkflowState) -> WorkflowState:
        return run_agent("feature_engineering_agent")(state)

    def sync_feature_store(state: WorkflowState) -> WorkflowState:
        return run_agent("feature_store_agent")(state)

    def infer(state: WorkflowState) -> WorkflowState:
        return run_agent("model_inference_agent")(state)

    def monitor(state: WorkflowState) -> WorkflowState:
        next_state = run_agent("monitoring_agent")(state)
        next_state.job.status = AgentStatus.FAILED if next_state.errors else AgentStatus.SUCCEEDED
        return next_state

    graph = StateGraph(WorkflowState)
    graph.add_node("intake", intake)
    graph.add_node("classify", classify)
    graph.add_node("extract", extract)
    graph.add_node("face_verify", face_verify)
    graph.add_node("validate", validate)
    graph.add_node("engineer_features", engineer_features)
    graph.add_node("sync_feature_store", sync_feature_store)
    graph.add_node("infer", infer)
    graph.add_node("monitor", monitor)

    graph.set_entry_point("intake")
    graph.add_edge("intake", "classify")
    graph.add_edge("classify", "extract")
    graph.add_edge("extract", "face_verify")
    graph.add_edge("face_verify", "validate")
    graph.add_edge("validate", "engineer_features")
    graph.add_edge("engineer_features", "sync_feature_store")
    graph.add_edge("sync_feature_store", "infer")
    graph.add_edge("infer", "monitor")
    graph.add_edge("monitor", END)

    return graph.compile()
