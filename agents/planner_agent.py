"""Planner Agent: decides execution order and strategy."""

from typing import List

from core.llm_client import LLMClient, llm
from core.schemas import AgentTrace, Incident
from core.tracing import TraceBuilder


class PlannerAgent:
    """Determines how to process a batch of incidents."""

    def __init__(self, llm_client: LLMClient = llm):
        self.llm = llm_client
        self.name = "planner"

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
        if self.llm.mock:
            return "Strategy: Process critical incidents first, then high/medium/low."

        prompt = (
            f"You are a site reliability planning assistant. "
            f"There are {len(incidents)} incidents. "
            f"Suggest a concise triage strategy in one sentence."
        )
        resp = self.llm.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=128,
        )
        return self.llm.extract_content(resp)

    def generate_plan_text(self, incident_count: int) -> str:
        """Return a judge-readable agentic plan."""
        if self.llm.mock:
            return (
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

        prompt = (
            "You are an AgentOps workflow planner. "
            "Describe a 7-step plan for triaging incidents that includes: "
            "schema validation, deterministic scoring, risk flag detection, baseline comparison, critic review, ROCm readiness, and final report assembly. "
            "Use markdown bullet points. Be concise."
        )
        resp = self.llm.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=256,
        )
        return self.llm.extract_content(resp)
