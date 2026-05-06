"""Deterministic strategy simulation and SLA evaluation for Command Center."""

from __future__ import annotations

from typing import Iterable, Optional

from core.benchmark_schemas import AmdBenchmarkSummary
from core.model_router import build_model_profiles
from core.schemas import SLAMonitorResult, TriageDecision, WorkflowStrategyResult

ESCALATION_PACKET_OVERHEAD_MS = 90.0

QUALITY_BASE = {
    "deterministic_only": 48.0,
    "small_model": 72.0,
    "large_model": 88.0,
}

COVERAGE_BASE = {
    "deterministic_only": 52.0,
    "small_model": 71.0,
    "large_model": 86.0,
}


def simulate_workflow_strategies(
    triage_decisions: Iterable[TriageDecision],
    *,
    current_benchmark: Optional[AmdBenchmarkSummary] = None,
    small_model_benchmark: Optional[AmdBenchmarkSummary] = None,
) -> list[WorkflowStrategyResult]:
    """Compare deterministic routing strategies without calling a live endpoint."""
    decisions = list(triage_decisions)
    profiles = build_model_profiles(current_benchmark, small_model_benchmark)
    benchmark_source = _build_benchmark_source(profiles)
    top_incident_ids = {decision.incident_id for decision in decisions[:3]}
    recommended_name = _pick_recommended_strategy(decisions)

    strategies = [
        ("Speed-first", "Keep automated latency low by reserving narratives for high-risk incidents."),
        ("Cost-first", "Prefer deterministic templates and use the smaller model only for the top incidents."),
        ("Quality-first", "Spend more latency budget to improve reasoning quality on high-risk incidents."),
        ("Safety-first", "Bias toward human review and richer critique on high and critical risk."),
        ("Balanced AMD Router", "Use verified AMD benchmark evidence to mix deterministic, small-model, large-model, and human review paths."),
    ]

    results: list[WorkflowStrategyResult] = []
    for strategy_name, description in strategies:
        total_latency_ms = 0.0
        total_cost_usd = 0.0
        human_review_count = 0
        model_calls = 0
        mode_counts = {"deterministic_only": 0, "small_model": 0, "large_model": 0}
        max_p95_latency_ms = float(profiles["deterministic_only"]["p95_latency_ms"])
        quality_total = 0.0
        coverage_total = 0.0
        weight_total = 0.0

        for decision in decisions:
            step = _select_strategy_step(strategy_name, decision, top_incident_ids)
            mode = step["mode"]
            human_review = step["human_review"]

            mode_counts[mode] += 1
            total_latency_ms += float(profiles[mode]["latency_ms"])
            max_p95_latency_ms = max(max_p95_latency_ms, float(profiles[mode]["p95_latency_ms"]))

            if mode != "deterministic_only":
                model_calls += 1
                total_cost_usd += float(profiles[mode]["cost_usd"])

            if human_review:
                human_review_count += 1
                total_latency_ms += ESCALATION_PACKET_OVERHEAD_MS

            risk_weight = _risk_weight(decision)
            quality_total += risk_weight * _quality_score(mode, human_review, decision)
            coverage_total += risk_weight * _coverage_score(mode, human_review, decision)
            weight_total += risk_weight

        expected_quality_score = round(quality_total / max(weight_total, 1.0), 1)
        risk_coverage_score = round(coverage_total / max(weight_total, 1.0), 1)

        results.append(
            WorkflowStrategyResult(
                strategy_name=strategy_name,
                description=description,
                total_estimated_latency_ms=round(total_latency_ms, 2),
                p95_latency_risk=_format_p95_risk(max_p95_latency_ms, human_review_count),
                estimated_cost_usd=round(total_cost_usd, 4),
                expected_quality_score=expected_quality_score,
                risk_coverage_score=risk_coverage_score,
                human_review_count=human_review_count,
                model_calls=model_calls,
                deterministic_steps=len(decisions),
                recommended=strategy_name == recommended_name,
                benchmark_source=benchmark_source,
                risks=_strategy_risks(strategy_name, decisions, mode_counts, human_review_count),
                rationale=_strategy_rationale(strategy_name, mode_counts, human_review_count),
            )
        )

    return results


def evaluate_sla_monitor(
    selected_strategy: WorkflowStrategyResult,
    benchmark_summary: Optional[AmdBenchmarkSummary],
    triage_decisions: Iterable[TriageDecision],
    *,
    fallback_count: int = 0,
    max_p95_latency_ms: float = 2500.0,
    min_success_rate: float = 0.95,
    max_fallback_count: int = 0,
    min_trust_score: float = 60.0,
) -> SLAMonitorResult:
    """Evaluate strategy readiness against deterministic SLA guardrails."""
    decisions = list(triage_decisions)
    thresholds = {
        "max_p95_latency_ms": max_p95_latency_ms,
        "min_success_rate": min_success_rate,
        "max_fallback_count": float(max_fallback_count),
        "min_trust_score": min_trust_score,
    }

    status = "PASS"
    summary_message = "Current benchmark, strategy, and runtime settings meet the default SLA guardrails."
    violations: list[str] = []
    mitigation: list[str] = []

    if benchmark_summary is None:
        status = "WARN"
        summary_message = "Benchmark evidence is missing, so live-routing claims should be treated as provisional."
        violations.append("Benchmark missing: AMD routing estimates are using fallback assumptions.")
        mitigation.append("Attach a verified benchmark before presenting latency or throughput claims.")
    else:
        success_rate = (
            benchmark_summary.successful_requests / benchmark_summary.total_requests
            if benchmark_summary.total_requests
            else 0.0
        )
        if success_rate < min_success_rate:
            status = "WARN"
            summary_message = "Benchmark reliability is below the target success-rate threshold."
            violations.append(
                f"Reliability warning: benchmark success rate is {success_rate:.2%}, below the {min_success_rate:.0%} target."
            )
            mitigation.append("Stabilize the endpoint before trusting live-routing estimates.")

        if benchmark_summary.p95_latency_ms > max_p95_latency_ms:
            status = "WARN"
            summary_message = "Benchmark p95 latency exceeds the SLA threshold."
            violations.append(
                f"Latency warning: benchmark p95 is {benchmark_summary.p95_latency_ms:.2f} ms, above the {max_p95_latency_ms:.0f} ms threshold."
            )
            mitigation.append("Reduce large-model volume or switch the recommendation to a faster strategy.")
        elif benchmark_summary.p95_latency_ms >= max_p95_latency_ms * 0.9 and status == "PASS":
            status = "PASS_WITH_WARNING"
            summary_message = (
                "p95 latency is close to the SLA threshold. Route low/medium-risk incidents to deterministic "
                "or smaller-model paths and reserve Qwen 7B for critical review."
            )
            mitigation.append(
                "Keep low and medium incidents on deterministic or Qwen 1.5B paths to preserve latency headroom."
            )

    if fallback_count > max_fallback_count:
        status = "WARN"
        summary_message = "Narrative runtime fallbacks were observed and should be corrected before operational use."
        violations.append(
            f"Runtime warning: {fallback_count} fallback event(s) were observed during narrative generation."
        )
        mitigation.append("Keep mock mode disabled only when the endpoint is healthy and authenticated.")

    low_trust_critical = [
        decision
        for decision in decisions
        if _is_critical(decision) and decision.trust_score < min_trust_score
    ]
    if low_trust_critical and selected_strategy.human_review_count < len(low_trust_critical):
        status = "FAIL"
        summary_message = "Critical low-trust incidents are not sufficiently covered by human review."
        violations.append(
            "Critical low-trust incidents exceed the strategy's human-review coverage."
        )
        mitigation.append("Use Safety-first or Balanced AMD Router to preserve human review for critical low-trust incidents.")

    if status == "PASS":
        mitigation.append(
            "Current benchmark, strategy, and runtime settings meet the default SLA guardrails."
        )

    return SLAMonitorResult(
        status=status,
        summary_message=summary_message,
        violations=violations,
        recommended_mitigation=mitigation,
        thresholds=thresholds,
    )


def _select_strategy_step(
    strategy_name: str,
    decision: TriageDecision,
    top_incident_ids: set[str],
) -> dict[str, object]:
    flag_codes = {flag.code for flag in decision.risk_flags}
    risk_tier = _risk_tier(decision)
    trust_low = decision.trust_score < 50
    critical_flags = bool({"HALLUCINATION_RISK", "SECURITY_WITHOUT_EVIDENCE"} & flag_codes)

    if strategy_name == "Speed-first":
        if critical_flags or trust_low:
            return {"mode": "deterministic_only", "human_review": True}
        if risk_tier == "high":
            return {"mode": "small_model", "human_review": False}
        return {"mode": "deterministic_only", "human_review": False}

    if strategy_name == "Cost-first":
        if risk_tier == "critical":
            return {"mode": "deterministic_only", "human_review": True}
        if decision.incident_id in top_incident_ids and risk_tier in {"high", "medium"}:
            return {"mode": "small_model", "human_review": False}
        return {"mode": "deterministic_only", "human_review": False}

    if strategy_name == "Quality-first":
        if risk_tier in {"critical", "high"}:
            return {"mode": "large_model", "human_review": trust_low or critical_flags}
        if risk_tier == "medium":
            return {"mode": "small_model", "human_review": False}
        return {"mode": "deterministic_only", "human_review": False}

    if strategy_name == "Safety-first":
        if risk_tier == "critical":
            return {"mode": "large_model", "human_review": True}
        if risk_tier == "high":
            return {"mode": "large_model", "human_review": critical_flags}
        if risk_tier == "medium":
            return {"mode": "small_model", "human_review": False}
        return {"mode": "deterministic_only", "human_review": False}

    if risk_tier == "critical":
        use_large_model = decision.system in {"payments", "database"} or critical_flags
        return {
            "mode": "large_model" if use_large_model else "small_model",
            "human_review": trust_low or critical_flags or decision.priority_score >= 85,
        }
    if risk_tier == "high":
        use_large_model = decision.system in {"payments", "database"} or "AMD_GPU_INFERENCE_DEGRADATION" in flag_codes
        return {"mode": "large_model" if use_large_model else "small_model", "human_review": False}
    if risk_tier == "medium":
        return {"mode": "small_model", "human_review": False}
    return {"mode": "deterministic_only", "human_review": False}


def _quality_score(mode: str, human_review: bool, decision: TriageDecision) -> float:
    score = QUALITY_BASE[mode]
    if human_review:
        score += 8.0
    if _is_critical(decision) and mode == "deterministic_only":
        score -= 12.0
    if _risk_tier(decision) == "high" and mode == "small_model":
        score -= 3.0
    return max(25.0, min(99.0, score))


def _coverage_score(mode: str, human_review: bool, decision: TriageDecision) -> float:
    score = COVERAGE_BASE[mode]
    if human_review:
        score += 12.0
    if _is_critical(decision) and not human_review:
        score -= 18.0
    if "AMD_GPU_INFERENCE_DEGRADATION" in {flag.code for flag in decision.risk_flags} and mode != "large_model":
        score -= 8.0
    return max(20.0, min(99.0, score))


def _strategy_risks(
    strategy_name: str,
    decisions: list[TriageDecision],
    mode_counts: dict[str, int],
    human_review_count: int,
) -> list[str]:
    risks: list[str] = []
    critical_count = sum(1 for decision in decisions if _is_critical(decision))
    if critical_count and human_review_count == 0:
        risks.append("Critical incidents are not human-gated under this strategy.")
    if mode_counts["large_model"] == 0 and any(_risk_tier(decision) == "high" for decision in decisions):
        risks.append("High-risk incidents do not get deep critique from the larger model.")
    if mode_counts["deterministic_only"] == len(decisions):
        risks.append("Narrative depth is limited to deterministic templates.")
    if strategy_name in {"Quality-first", "Safety-first"}:
        risks.append("Higher dependence on Qwen 7B increases latency and cost exposure.")
    if strategy_name == "Speed-first":
        risks.append("High-risk incidents may lose nuance because they stay off the larger model.")
    if not risks:
        risks.append("Strategy is balanced but still depends on benchmark health for live expectations.")
    return risks


def _strategy_rationale(
    strategy_name: str,
    mode_counts: dict[str, int],
    human_review_count: int,
) -> str:
    if strategy_name == "Speed-first":
        return "Optimizes for lower latency by keeping most incidents deterministic and using smaller-model summaries selectively."
    if strategy_name == "Cost-first":
        return "Minimizes narrative spend and reserves the smaller model for only the highest-ranked non-critical work."
    if strategy_name == "Quality-first":
        return "Pushes more incidents through Qwen 7B to maximize reasoning quality at the expense of latency."
    if strategy_name == "Safety-first":
        return "Emphasizes human validation and richer critique on critical and high-risk workflows."
    return (
        f"Combines {mode_counts['small_model']} smaller-model summaries, "
        f"{mode_counts['large_model']} larger-model critiques, and {human_review_count} human-review gates using AMD benchmark evidence."
    )


def _build_benchmark_source(profiles: dict[str, dict[str, object]]) -> str:
    large_source = str(profiles["large_model"]["source"])
    small_source = str(profiles["small_model"]["source"])
    return f"Large-model source: {large_source}; Small-model source: {small_source}"


def _pick_recommended_strategy(decisions: list[TriageDecision]) -> str:
    low_trust_critical = [
        decision for decision in decisions if _is_critical(decision) and decision.trust_score < 60
    ]
    if len(low_trust_critical) >= 2:
        return "Safety-first"
    return "Balanced AMD Router"


def _risk_weight(decision: TriageDecision) -> float:
    tier = _risk_tier(decision)
    if tier == "critical":
        return 1.8
    if tier == "high":
        return 1.4
    if tier == "medium":
        return 1.1
    return 0.8


def _risk_tier(decision: TriageDecision) -> str:
    flag_codes = {flag.code for flag in decision.risk_flags}
    if _is_critical(decision):
        return "critical"
    if "AMD_GPU_INFERENCE_DEGRADATION" in flag_codes or decision.priority_score >= 60:
        return "high"
    if decision.priority_score >= 45:
        return "medium"
    return "low"


def _is_critical(decision: TriageDecision) -> bool:
    flag_codes = {flag.code for flag in decision.risk_flags}
    return (
        decision.priority_score >= 85
        or decision.trust_score < 50
        or "HALLUCINATION_RISK" in flag_codes
        or "SECURITY_WITHOUT_EVIDENCE" in flag_codes
    )


def _format_p95_risk(max_p95_latency_ms: float, human_review_count: int) -> str:
    if max_p95_latency_ms <= 1500:
        label = "low"
    elif max_p95_latency_ms <= 2500:
        label = "guarded"
    else:
        label = "elevated"

    if human_review_count:
        label = f"{label}, human-gated"
    return f"{max_p95_latency_ms:.0f} ms ({label})"
