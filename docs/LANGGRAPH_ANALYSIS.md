# LangGraph Analysis

| Component | Source location | Purpose | Dependencies | Recommended source of truth | Migration strategy | Risk |
| --- | --- | --- | --- | --- | --- | --- |
| Basic graph | `2_multi_agent_pipeline/credit_scoring_pipeline/main_graph.py` | Sequential `fetch_data -> write_to_feast` graph wrapped with Prefect tasks | LangGraph, Prefect | No | Keep as legacy demo; replace usage with async graph from MCP module | Medium: calls undefined `data_fetching_agent_node` |
| Async graph | `2_multi_agent_pipeline/credit_scoring_pipeline/mcp/mcp_server.py` | Concurrent document fetch node, then feature engineering node | LangGraph, asyncio, Prefect task `.fn` calls | Yes, current graph source | Refactor nodes to invoke MCP tools, but preserve async fan-out and state fields | Medium |
| Prefect orchestrator | `2_multi_agent_pipeline/credit_scoring_pipeline/flows/orchestrator.py` | Normalizes paths and invokes `create_graph().ainvoke()` inside Prefect flow | Prefect, `mcp.mcp_server.create_graph` | Yes, current batch workflow entry | Preserve path validation and Prefect deployment; shift graph internals to MCP calls | Low |
| Platform graph | `ai_platform/orchestration/graph.py` | Shared workflow state graph added in architecture phase | LangGraph | Orchestration contract only | Use as integration target after legacy graph is wrapped | Medium |

## Existing Nodes

| Node | Source | Function | Behavior |
| --- | --- | --- | --- |
| `fetch` | `mcp/mcp_server.py` | `fetch_node` | Runs `data_fetching_agent_task.fn(path)` concurrently with `asyncio.gather`; normalizes list results to dicts |
| `feature_engineer` | `mcp/mcp_server.py` | `feature_engineering_node` | Runs `feature_engineering_agent_task.fn(state["batch_data"])` |
| `fetch_data` | `main_graph.py` | `fetch_data_task.fn` | Legacy sequential fetch wrapper |
| `write_to_feast` | `main_graph.py` | `write_to_feast_task.fn` | Legacy Feast writer wrapper |

## Required Refactor

Do not move orchestration into Celery. Refactor LangGraph nodes to call MCP tools, which then dispatch Celery where needed:

`LangGraph node -> MCP tool invocation -> Celery task/group/chord -> DB/Feast/model`

The first integration target should be the existing async graph because it already supports concurrent document processing.
