"""Planner Agent: decides execution order and strategy."""

from typing import List

from core.llm_client import LLMClient, llm
from core.schemas import Incident
from core.tracing import TraceBuilder


class PlannerAgent:
    """Determines how to process a batch of incidents."""

    SYSTEM_PROMPT = (
        "You are a senior AI operations planner. Create concise execution plans for "
        "auditable incident triage workflows. Do not change deterministic scores."
    )

    def __init__(self, llm_client: LLMClient = llm):
        self.llm = llm_client
        self.name = "planner"
        self.last_llm_meta = None

    def plan(self, incidents: List[Incident], trace_builder: TraceBuilder) -> List[str]:
        """Return ordered list of incident IDs to process."""
        trace_builder.start_step("plan", self.name, input_summary=f"{len(incidents)} incidents")

        # Deterministic: critical -> high -> medium -> low, then by reported_at
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        ordered = sorted(
            incidents,
            key=lambda i: (severity_order.get(i.severity_hint.value, 99), i.reported_at),
        )
        plan = [i.id for i in ordered]

        trace_builder.end_step(
            output_summary=f"Plan: {plan}",
            status="success",
        )
        return plan

    def summarize_strategy(self, incidents: List[Incident]) -> str:
        """Optional LLM-based strategy summary."""
        fallback = "Strategy: Process critical incidents first, then high/medium/low."
        user_prompt = (
            f"You are a site reliability planning assistant. "
            f"There are {len(incidents)} incidents. "
            f"Suggest a concise triage strategy in one sentence."
        )
        result = self.llm.chat(self.SYSTEM_PROMPT, user_prompt, fallback=fallback)
        self.last_llm_meta = result
        return result["content"]

    def generate_plan_text(self, incident_count: int) -> str:
        """Return an operator-readable agentic plan."""
        fallback = (
            "**AgentOps Execution Plan**\n\n"
            "1. Validate incident schema and required fields.\n"
            "2. Compute deterministic priority score using users, revenue, SLA, severity, system criticality, and status.\n"
            "3. Detect risk flags (missing evidence, contradictory data, hallucination, security gaps, AMD/ROCm issues).\n"
            "4. Compare against a naive baseline that only uses severity and affected users.\n"
            "5. Generate critic review for top-priority incidents.\n"
            "6. Produce AMD/ROCm readiness report when inference incidents are present.\n"
            "7. Assemble final audit report with trace, optimizations, and cost estimates.\n"
            f"\n*Processing {incident_count} incidents in deterministic mode with optional LLM explanations.*"
        )

        user_prompt = (
            f"Create a concise 7-step execution plan for triaging {incident_count} incidents. "
            "Include: schema validation, deterministic scoring, risk flag detection, "
            "baseline comparison, critic review, ROCm readiness, and final report assembly. "
            "Use markdown bullet points. Be concise."
        )

        result = self.llm.chat(self.SYSTEM_PROMPT, user_prompt, fallback=fallback)
        self.last_llm_meta = result
        return result["content"]
