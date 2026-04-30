"""Trust, confidence, and cost scoring utilities."""

import hashlib
from typing import List

from core.schemas import Incident, TriageResult


def compute_confidence(result: TriageResult, incidents: List[Incident]) -> float:
    """Deterministic confidence heuristic based on result quality."""
    score = 0.5

    # More reasoning text = slightly higher confidence
    if len(result.reasoning) > 50:
        score += 0.1
    if len(result.reasoning) > 150:
        score += 0.05

    # Presence of risk flags shows awareness
    if result.risk_flags:
        score += 0.05 * min(len(result.risk_flags), 3)

    # Recommendations present
    if result.recommendations:
        score += 0.05 * min(len(result.recommendations), 2)

    # Penalize very high latency estimates
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
    # Assume $2 per 1M tokens and $0.01 per 1s latency for compute
    token_cost = (token_count / 1_000_000) * 2.0
    compute_cost = (latency_ms / 1000) * 0.01
    return round(token_cost + compute_cost, 4)


def deterministic_score_seed(text: str) -> float:
    """Generate a stable pseudo-random score from text for mock demos."""
    digest = hashlib.sha256(text.encode()).hexdigest()
    val = int(digest[:8], 16) / 0xFFFFFFFF
    return round(0.5 + 0.4 * val, 3)
