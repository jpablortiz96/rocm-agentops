"""Deterministic incident scoring, trust scoring, risk flags, and recommendations."""

import hashlib
from typing import Dict, List

from core.schemas import BaselineDecision, Incident, RiskFlag, TriageResult


# ---------------------------------------------------------------------------
# Legacy helpers (kept for backward compatibility with agent files)
# ---------------------------------------------------------------------------

def compute_confidence(result: TriageResult, incidents: List[Incident]) -> float:
    """Deterministic confidence heuristic based on result quality."""
    score = 0.5
    if len(result.reasoning) > 50:
        score += 0.1
    if len(result.reasoning) > 150:
        score += 0.05
    if result.risk_flags:
        score += 0.05 * min(len(result.risk_flags), 3)
    if result.recommendations:
        score += 0.05 * min(len(result.recommendations), 2)
    if result.estimated_latency_ms > 5000:
        score -= 0.1
    return round(min(max(score, 0.0), 1.0), 3)


def compute_overall_trust(triage_results: List[TriageResult]) -> float:
    """Aggregate trust score across all triage results."""
    if not triage_results:
        return 0.0
    avg = sum(r.confidence_score for r in triage_results) / len(triage_results)
    return round(min(max(avg, 0.0), 1.0), 3)


def estimate_cost(latency_ms: int, token_count: int = 500) -> float:
    """Rough cost estimate in USD (mock pricing)."""
    token_cost = (token_count / 1_000_000) * 2.0
    compute_cost = (latency_ms / 1000) * 0.01
    return round(token_cost + compute_cost, 4)


def deterministic_score_seed(text: str) -> float:
    """Generate a stable pseudo-random score from text for mock demos."""
    digest = hashlib.sha256(text.encode()).hexdigest()
    val = int(digest[:8], 16) / 0xFFFFFFFF
    return round(0.5 + 0.4 * val, 3)


# ---------------------------------------------------------------------------
# New deterministic scoring engine
# ---------------------------------------------------------------------------

_SYSTEM_CRITICALITY = {
    "payments": 15,
    "authentication": 13,
    "security": 13,
    "database": 13,
    "inference": 12,
    "api": 10,
    "data_pipeline": 8,
    "deployment": 7,
    "frontend": 6,
    "customer_support": 4,
}

_SEVERITY_SCORES = {
    "critical": 15,
    "high": 11,
    "medium": 6,
    "low": 2,
}

_STATUS_SCORES = {
    "open": 10,
    "investigating": 8,
    "monitoring": 5,
    "mitigated": 2,
}


def _score_affected_users(n: int) -> int:
    if n >= 100_000:
        return 20
    if n >= 50_000:
        return 16
    if n >= 10_000:
        return 12
    if n >= 1_000:
        return 8
    if n > 0:
        return 4
    return 0


def _score_revenue(v: float) -> int:
    if v >= 100_000:
        return 20
    if v >= 50_000:
        return 16
    if v >= 10_000:
        return 12
    if v >= 1_000:
        return 6
    if v > 0:
        return 3
    return 0


def _score_sla(minutes: int) -> int:
    if minutes <= 10:
        return 20
    if minutes <= 30:
        return 16
    if minutes <= 60:
        return 12
    if minutes <= 120:
        return 8
    if minutes <= 240:
        return 4
    return 0


def _has_contradictory_data(incident: Incident) -> bool:
    """Detect imperfect / contradictory signals."""
    if incident.severity_hint.value == "low" and incident.affected_users > 50_000:
        return True
    if incident.affected_users == 0 and incident.revenue_impact_usd > 50_000:
        return True
    if incident.status.value == "mitigated" and _compute_raw_priority(incident) > 60:
        return True
    return False


def _compute_raw_priority(incident: Incident) -> int:
    """Compute the raw priority score before confidence adjustments."""
    return (
        _score_affected_users(incident.affected_users)
        + _score_revenue(incident.revenue_impact_usd)
        + _score_sla(incident.sla_minutes_remaining)
        + _SEVERITY_SCORES.get(incident.severity_hint.value, 0)
        + _SYSTEM_CRITICALITY.get(incident.system, 5)
        + _STATUS_SCORES.get(incident.status.value, 0)
    )


def _compute_confidence(incident: Incident) -> float:
    """Confidence score 0-100."""
    score = 70.0

    # Evidence contribution
    evidence_count = len(incident.evidence)
    if evidence_count > 0:
        score += min(evidence_count * 5, 20)
    else:
        score -= 25.0

    # Contradictions
    if _has_contradictory_data(incident):
        score -= 10.0

    # Critical severity with weak evidence
    if incident.severity_hint.value == "critical" and evidence_count < 2:
        score -= 10.0

    return max(0.0, min(100.0, score))


def _compute_trust(incident: Incident, confidence: float, risk_flags: List[RiskFlag]) -> float:
    """Trust score 0-100."""
    evidence_count = len(incident.evidence)
    evidence_quality = min(evidence_count * 5, 20)
    consistency = 20.0 if not _has_contradictory_data(incident) else 10.0
    deterministic_validation = 10.0

    score = (
        confidence * 0.5
        + evidence_quality
        + consistency
        + deterministic_validation
    )

    # Penalty for risk flags
    critical_flags = [f for f in risk_flags if f.severity == "critical"]
    high_flags = [f for f in risk_flags if f.severity == "high"]
    score -= len(critical_flags) * 10.0
    score -= len(high_flags) * 5.0
    score -= max(0, len(risk_flags) - len(critical_flags) - len(high_flags)) * 2.0

    return max(0.0, min(100.0, score))


def _build_risk_flags(incident: Incident, priority_score: float, confidence_score: float) -> List[RiskFlag]:
    flags: List[RiskFlag] = []

    if len(incident.evidence) == 0:
        flags.append(RiskFlag(
            code="MISSING_EVIDENCE",
            label="MISSING_EVIDENCE",
            severity="high",
            explanation="No evidence items attached to this incident."
        ))

    if incident.severity_hint.value == "low" and incident.affected_users > 50_000:
        flags.append(RiskFlag(
            code="HIGH_USERS_LOW_SEVERITY",
            label="HIGH_USERS_LOW_SEVERITY",
            severity="medium",
            explanation="Low severity but very high user impact."
        ))

    if incident.affected_users == 0 and incident.revenue_impact_usd > 50_000:
        flags.append(RiskFlag(
            code="HIGH_REVENUE_LOW_USERS",
            label="HIGH_REVENUE_LOW_USERS",
            severity="medium",
            explanation="High revenue impact reported with zero affected users."
        ))

    if incident.status.value == "mitigated" and priority_score > 60:
        flags.append(RiskFlag(
            code="RESIDUAL_RISK_AFTER_MITIGATION",
            label="RESIDUAL_RISK_AFTER_MITIGATION",
            severity="high",
            explanation="Status is mitigated yet computed priority remains elevated."
        ))

    if incident.sla_minutes_remaining <= 10:
        flags.append(RiskFlag(
            code="URGENT_SLA",
            label="URGENT_SLA",
            severity="critical",
            explanation="Less than 10 minutes remain before SLA breach."
        ))

    if incident.system == "security" and len(incident.evidence) == 0:
        flags.append(RiskFlag(
            code="SECURITY_WITHOUT_EVIDENCE",
            label="SECURITY_WITHOUT_EVIDENCE",
            severity="critical",
            explanation="Security incident lacks supporting evidence."
        ))

    lowered_text = f"{incident.title} {incident.description}".lower()
    if incident.system == "inference" and "hallucination" in lowered_text:
        flags.append(RiskFlag(
            code="HALLUCINATION_RISK",
            label="HALLUCINATION_RISK",
            severity="critical",
            explanation="Inference incident involves model hallucination."
        ))

    if incident.system == "inference" and any(k in lowered_text for k in ("mi300x", "rocm", "throughput", "thermal", "triton", "gpu")):
        flags.append(RiskFlag(
            code="AMD_GPU_INFERENCE_DEGRADATION",
            label="AMD_GPU_INFERENCE_DEGRADATION",
            severity="high",
            explanation="AMD/ROCm inference stack affected."
        ))

    if priority_score >= 80:
        flags.append(RiskFlag(
            code="CRITICAL_PRIORITY",
            label="CRITICAL_PRIORITY",
            severity="high",
            explanation="Computed priority score is 80 or above."
        ))

    if confidence_score < 50:
        flags.append(RiskFlag(
            code="LOW_CONFIDENCE",
            label="LOW_CONFIDENCE",
            severity="medium",
            explanation="Confidence in available data is below 50%."
        ))

    return flags


def _recommended_action(priority_score: float, human_review_required: bool, status: str) -> str:
    if priority_score >= 85:
        return "Page on-call immediately"
    if human_review_required:
        return "Escalate to human incident commander"
    if status in ("mitigated", "monitoring"):
        return "Monitor and verify mitigation"
    if priority_score >= 45:
        return "Investigate within SLA"
    return "Batch for later review"


def _human_review_required(incident: Incident, priority_score: float, confidence_score: float, risk_flags: List[RiskFlag]) -> bool:
    if priority_score >= 80:
        return True
    if confidence_score < 50:
        return True
    if any(f.severity == "critical" for f in risk_flags):
        return True
    if incident.system == "security" and len(incident.evidence) == 0:
        return True
    if incident.system == "inference" and "hallucination" in f"{incident.title} {incident.description}".lower():
        return True
    return False


def calculate_incident_priority_score(incident: Incident) -> Dict:
    """Return a comprehensive deterministic score dict for an incident."""
    priority_score = float(_compute_raw_priority(incident))

    # Security escalation boost for critical + missing evidence + urgent SLA
    if (
        incident.system == "security"
        and incident.severity_hint.value == "critical"
        and len(incident.evidence) == 0
        and incident.sla_minutes_remaining <= 10
    ):
        priority_score += 15.0

    confidence_score = _compute_confidence(incident)
    risk_flags = _build_risk_flags(incident, priority_score, confidence_score)
    trust_score = _compute_trust(incident, confidence_score, risk_flags)
    human_review = _human_review_required(incident, priority_score, confidence_score, risk_flags)
    action = _recommended_action(priority_score, human_review, incident.status.value)

    reasons = [
        f"Affected users score: {_score_affected_users(incident.affected_users)}/20",
        f"Revenue impact score: {_score_revenue(incident.revenue_impact_usd)}/20",
        f"SLA urgency score: {_score_sla(incident.sla_minutes_remaining)}/20",
        f"Severity score: {_SEVERITY_SCORES.get(incident.severity_hint.value, 0)}/15",
        f"System criticality score: {_SYSTEM_CRITICALITY.get(incident.system, 5)}/15",
        f"Status residual score: {_STATUS_SCORES.get(incident.status.value, 0)}/10",
        f"Evidence count: {len(incident.evidence)}",
    ]

    if _has_contradictory_data(incident):
        reasons.append("Contradictory signals detected in incident data.")

    return {
        "priority_score": round(priority_score, 1),
        "confidence_score": round(confidence_score, 1),
        "trust_score": round(trust_score, 1),
        "reasons": reasons,
        "risk_flags": risk_flags,
        "human_review_required": human_review,
        "recommended_action": action,
    }



def run_baseline_triage(incidents: List[Incident]) -> List[BaselineDecision]:
    """Naive baseline triage using only severity and affected_users."""
    severity_weights = {"critical": 100, "high": 75, "medium": 50, "low": 25}
    scored = []
    for inc in incidents:
        score = severity_weights.get(inc.severity_hint.value, 0) + (inc.affected_users / 1000.0)
        scored.append((inc, score))
    scored.sort(key=lambda x: x[1], reverse=True)
    results: List[BaselineDecision] = []
    for rank, (inc, score) in enumerate(scored, start=1):
        results.append(
            BaselineDecision(
                incident_id=inc.id,
                title=inc.title,
                system=inc.system,
                severity_hint=inc.severity_hint.value,
                affected_users=inc.affected_users,
                baseline_score=round(score, 1),
                baseline_rank=rank,
            )
        )
    return results
