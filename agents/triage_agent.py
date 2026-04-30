"""Triage Agent: rank incidents and produce reasoning."""

from typing import List

from core.llm_client import LLMClient, llm
from core.schemas import Incident, TriageResult
from core.scoring import compute_confidence, deterministic_score_seed, estimate_cost
from core.tracing import TraceBuilder


class TriageAgent:
    """Produces priority ranking, reasoning, and risk flags for incidents."""

    def __init__(self, llm_client: LLMClient = llm):
        self.llm = llm_client
        self.name = "triage"

    def triage(
        self,
        incident: Incident,
        rank: int,
        trace_builder: TraceBuilder,
    ) -> TriageResult:
        """Run triage on a single incident."""
        trace_builder.start_step(
            "triage_incident", self.name, input_summary=f"{incident.id}: {incident.title}"
        )

        reasoning = self._generate_reasoning(incident)
        risk_flags = self._extract_risk_flags(incident)
        recommendations = self._extract_recommendations(incident)

        latency_ms = self._estimate_latency(incident)
        cost = estimate_cost(latency_ms)

        result = TriageResult(
            incident_id=incident.id,
            priority_rank=rank,
            reasoning=reasoning,
            risk_flags=risk_flags,
            confidence_score=0.0,  # filled later
            estimated_cost_usd=cost,
            estimated_latency_ms=latency_ms,
            assigned_team=self._suggest_team(incident),
            recommendations=recommendations,
        )
        result.confidence_score = compute_confidence(result, [incident])

        trace_builder.end_step(
            output_summary=f"Rank {rank}, confidence {result.confidence_score}",
            status="success",
        )
        return result

    def _generate_reasoning(self, incident: Incident) -> str:
        if self.llm.mock:
            return (
                f"Incident '{incident.title}' in {incident.system} ({incident.severity_hint.value}) "
                f"requires attention due to {len(incident.evidence)} flagged symptoms."
            )
        prompt = (
            f"Incident: {incident.title}\nDescription: {incident.description}\n"
            f"Severity: {incident.severity_hint.value}\nService: {incident.system}\n"
            f"Provide a one-sentence reasoning for priority."
        )
        resp = self.llm.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=128,
        )
        return self.llm.extract_content(resp)

    def _extract_risk_flags(self, incident: Incident) -> List[str]:
        flags = []
        if incident.severity_hint.value == "critical":
            flags.append("customer_impact")
        if "database" in incident.title.lower() or "database" in incident.description.lower():
            flags.append("data_integrity")
        if "payment" in incident.title.lower():
            flags.append("revenue_at_risk")
        if incident.status.value == "open":
            flags.append("unattended")
        return flags

    def _extract_recommendations(self, incident: Incident) -> List[str]:
        recs = []
        if incident.severity_hint.value in ("critical", "high"):
            recs.append("Escalate to on-call immediately")
        if "cpu" in incident.description.lower() or "memory" in incident.description.lower():
            recs.append("Check resource utilization dashboards")
        if not recs:
            recs.append("Monitor and update status")
        return recs

    def _estimate_latency(self, incident: Incident) -> int:
        base = 200
        if incident.severity_hint.value == "critical":
            base += 400
        elif incident.severity_hint.value == "high":
            base += 200
        seed = deterministic_score_seed(incident.id)
        return base + int(seed * 300)

    def _suggest_team(self, incident: Incident) -> str:
        lowered = f"{incident.title} {incident.description}".lower()
        if "api" in lowered or "gateway" in lowered:
            return "platform"
        if "database" in lowered or "storage" in lowered:
            return "data"
        if "frontend" in lowered or "ui" in lowered:
            return "product"
        return "sre"
