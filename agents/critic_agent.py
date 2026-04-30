"""Critic Agent: reviews triage results for trust and quality."""

from typing import List

from core.llm_client import LLMClient, llm
from core.schemas import Incident, TriageDecision, TriageResult
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

    def review_batch(self, triage_decisions: List[TriageDecision]) -> str:
        """Return judge-readable critique of the top incidents."""
        if not triage_decisions:
            return "No incidents to review."

        top = [d for d in triage_decisions if d.priority_score >= 60]
        low_trust_high_priority = [d for d in top if d.trust_score < 50]
        missing_evidence = [d for d in triage_decisions if not d.risk_flags or all(f.code != "MISSING_EVIDENCE" for f in d.risk_flags)]
        # Actually find ones WITH missing evidence:
        missing_evidence = [d for d in triage_decisions if any(f.code == "MISSING_EVIDENCE" for f in d.risk_flags)]
        hallucination = [d for d in triage_decisions if any(f.code == "HALLUCINATION_RISK" for f in d.risk_flags)]
        security = [d for d in triage_decisions if any(f.code == "SECURITY_WITHOUT_EVIDENCE" for f in d.risk_flags)]
        human_review = [d for d in triage_decisions if d.human_review_required]

        if self.llm.mock:
            lines = ["**Critic Review**\n"]
            lines.append(f"Reviewed {len(triage_decisions)} incidents. {len(human_review)} require human review.\n")

            if low_trust_high_priority:
                lines.append("**Low Trust + High Priority:**")
                for d in low_trust_high_priority:
                    lines.append(f"- {d.incident_id}: priority={d.priority_score}, trust={d.trust_score} — data quality is insufficient for the rank.")
                lines.append("")

            if missing_evidence:
                lines.append("**Missing Evidence:**")
                for d in missing_evidence:
                    lines.append(f"- {d.incident_id}: {d.title} — no supporting evidence attached.")
                lines.append("")

            if hallucination:
                lines.append("**Hallucination Risk:**")
                for d in hallucination:
                    lines.append(f"- {d.incident_id}: {d.title} — model hallucination requires immediate human review.")
                lines.append("")

            if security:
                lines.append("**Security Escalation:**")
                for d in security:
                    lines.append(f"- {d.incident_id}: {d.title} — security incident with missing evidence is a critical gap.")
                lines.append("")

            if human_review:
                lines.append("**Human Review Required:**")
                for d in human_review:
                    lines.append(f"- {d.incident_id}: {d.title} — action: {d.recommended_action}")
                lines.append("")

            return "\n".join(lines)

        prompt = (
            "You are a senior SRE critic reviewing triage decisions. "
            "Highlight incidents with low trust but high priority, missing evidence, hallucination risk, or security gaps. "
            "List which ones require human review and why. Use markdown bullets. Be concise."
        )
        resp = self.llm.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=512,
        )
        return self.llm.extract_content(resp)
