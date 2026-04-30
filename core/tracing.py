"""Agent trace builder and timeline utilities."""

import time
import uuid
from datetime import datetime
from typing import Optional

from core.schemas import AgentStep, AgentTrace


class TraceBuilder:
    """Build an AgentTrace incrementally."""

    def __init__(self, workflow_name: str, trace_id: Optional[str] = None):
        self.trace = AgentTrace(
            trace_id=trace_id or f"trace-{uuid.uuid4().hex[:12]}",
            workflow_name=workflow_name,
            started_at=datetime.utcnow(),
        )
        self._current_step_start: Optional[float] = None
        self._current_step: Optional[AgentStep] = None

    def start_step(self, step_name: str, agent_name: str, input_summary: str = "") -> "TraceBuilder":
        self._current_step_start = time.time()
        self._current_step = AgentStep(
            step_name=step_name,
            agent_name=agent_name,
            input_summary=input_summary,
            output_summary="",
        )
        return self

    def end_step(self, output_summary: str = "", status: str = "success") -> "TraceBuilder":
        if self._current_step is None or self._current_step_start is None:
            return self
        finished = time.time()
        self._current_step.finished_at = datetime.utcnow()
        self._current_step.output_summary = output_summary
        self._current_step.status = status
        self._current_step.latency_ms = int((finished - self._current_step_start) * 1000)
        self.trace.add_step(self._current_step)
        self._current_step = None
        self._current_step_start = None
        return self

    def finalize(self) -> AgentTrace:
        self.trace.finished_at = datetime.utcnow()
        return self.trace

    def to_dataframe_rows(self):
        """Return list of dicts suitable for pandas DataFrame."""
        rows = []
        for step in self.trace.steps:
            rows.append(
                {
                    "Step": step.step_name,
                    "Agent": step.agent_name,
                    "Status": step.status,
                    "Latency (ms)": step.latency_ms,
                    "Input": step.input_summary[:100],
                    "Output": step.output_summary[:100],
                }
            )
        return rows
