"""Critic Agent: reviews triage results for trust and quality."""

from typing import List

from core.llm_client import LLMClient, llm
from core.schemas import Incident, TriageResult
from core.scoring import compute_confidence
from core.tracing import TraceBuilder


class CriticAgent:
    """Audits triage results and proposes adjustments."""

    def __init__(self, llm_client: LLMClient = llm):
        self.llm = llm_client
        self.name = "critic"

    def review(
        self,
        incident: Incident,
        result: TriageResult,
        trace_builder: TraceBuilder,
    ) -> TriageResult:
        """Review and optionally adjust a triage result."""
        trace_builder.start_step(
            "review", self.name, input_summary=f"Review {incident.id}"
        )

        # Deterministic checks
        issues: List[str] = []
        if result.priority_rank <= 2 and result.confidence_score < 0.6:
            issues.append("High priority with low confidence")
        if not result.risk_flags:
            issues.append("No risk flags identified")
        if result.estimated_latency_ms > 3000:
            issues.append("Latency estimate seems high for triage")

        # Simple adjustment: boost confidence if no issues found
        if not issues:
            adjustment = 0.05
        else:
            adjustment = -0.05 * len(issues)

        result.confidence_score = round(
            min(max(result.confidence_score + adjustment, 0.0), 1.0), 3
        )

        if self.llm.mock:
            review_note = (
                f"Review complete. {len(issues)} issues found. "
                f"Confidence adjusted to {result.confidence_score}."
            )
        else:
            prompt = (
                f"Review this triage result for incident {incident.id}:\n"
                f"Reasoning: {result.reasoning}\n"
                f"Flags: {result.risk_flags}\n"
                f"Provide a one-sentence review note."
            )
            resp = self.llm.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=128,
            )
            review_note = self.llm.extract_content(resp)

        trace_builder.end_step(
            output_summary=review_note,
            status="success",
        )
        return result
