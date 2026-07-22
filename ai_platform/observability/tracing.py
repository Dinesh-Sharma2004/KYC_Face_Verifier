"""Trace helpers shared by agents.

The recorder returns serializable trace records. Persistence is intentionally
left to the caller so existing database ownership is not changed implicitly.
"""

from contextlib import contextmanager
from datetime import UTC, datetime
from time import perf_counter
from typing import Dict, Iterator, List, Optional

from ai_platform.contracts.schemas import AgentExecutionTrace


class AgentTraceRecorder:
    def __init__(self, trace_id: str, job_id: str):
        self.trace_id = trace_id
        self.job_id = job_id

    @contextmanager
    def trace(
        self,
        agent_name: str,
        retries: int = 0,
        tool_calls: Optional[List[Dict]] = None,
    ) -> Iterator[AgentExecutionTrace]:
        start = datetime.now(UTC)
        started = perf_counter()
        record = AgentExecutionTrace(
            trace_id=self.trace_id,
            job_id=self.job_id,
            agent_name=agent_name,
            start_time=start,
            retries=retries,
            tool_calls=tool_calls or [],
        )

        try:
            yield record
            record.success = True
        except Exception as exc:
            record.success = False
            record.failure_reason = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            record.end_time = datetime.now(UTC)
            record.execution_time_ms = round((perf_counter() - started) * 1000, 3)
