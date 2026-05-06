"""Deterministic model routing for the ROCm AgentOps Command Center."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Iterable, Mapping, Optional

from core.benchmark_schemas import AmdBenchmarkSummary
from core.benchmarking import load_benchmark_results
from core.schemas import Incident, ModelRouteDecision, TriageDecision

SMALL_MODEL_NAME = "Qwen/Qwen2.5-1.5B-Instruct"
LARGE_MODEL_NAME = "Qwen/Qwen2.5-7B-Instruct"

OWNERS_PATH = "data/owners.json"
QWEN15B_BENCHMARK_PATH = "data/amd_benchmark_results_qwen15b.json"
QWEN7B_BENCHMARK_PATH = "data/amd_benchmark_results_qwen7b.json"

DEFAULT_OWNER = {
    "owner_name": "Operations Commander",
    "owner_email": "ops@example.com",
    "slack_channel": "#operations",
}

DEFAULT_PROFILES: Dict[str, Dict[str, object]] = {
    "deterministic_only": {
        "latency_ms": 35.0,
        "p95_latency_ms": 45.0,
        "cost_usd": 0.0,
        "source": "Local deterministic/template estimate",
        "estimated": False,
    },
    "small_model": {
        "latency_ms": 820.0,
        "p95_latency_ms": 1300.0,
        "cost_usd": 0.0006,
        "source": "Conservative simulated estimate for Qwen 1.5B",
        "estimated": True,
    },
    "large_model": {
        "latency_ms": 1750.0,
        "p95_latency_ms": 2600.0,
        "cost_usd": 0.0018,
        "source": "Conservative simulated estimate for Qwen 7B",
        "estimated": True,
    },
}

MODEL_RATE_USD_PER_MTOKEN = {
    SMALL_MODEL_NAME: 0.90,
    LARGE_MODEL_NAME: 1.80,
}


def load_owner_directory(path: str = OWNERS_PATH) -> Dict[str, Dict[str, str]]:
    """Load the static system owner directory from disk."""
    owner_path = Path(path)
    if not owner_path.exists():
        return {}
    try:
        return json.loads(owner_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def get_owner_for_system(system: str, owners: Optional[Mapping[str, Mapping[str, str]]] = None) -> Dict[str, str]:
    """Return owner metadata for a system, falling back to a generic owner."""
    directory = dict(owners or load_owner_directory())
    owner = directory.get(system, DEFAULT_OWNER)
    return {
        "owner_name": owner.get("owner_name", DEFAULT_OWNER["owner_name"]),
        "owner_email": owner.get("owner_email", DEFAULT_OWNER["owner_email"]),
        "slack_channel": owner.get("slack_channel", DEFAULT_OWNER["slack_channel"]),
    }


def build_model_profiles(
    current_benchmark: Optional[AmdBenchmarkSummary] = None,
    small_model_benchmark: Optional[AmdBenchmarkSummary] = None,
) -> Dict[str, Dict[str, object]]:
    """Build latency and cost profiles from verified benchmarks when available."""
    profiles = {
        key: value.copy() for key, value in DEFAULT_PROFILES.items()
    }

    large_benchmark = _select_large_model_benchmark(current_benchmark)
    small_benchmark = _select_small_model_benchmark(small_model_benchmark)

    if large_benchmark is not None:
        profiles["large_model"] = _benchmark_profile(large_benchmark, LARGE_MODEL_NAME)

    if small_benchmark is not None:
        profiles["small_model"] = _benchmark_profile(small_benchmark, SMALL_MODEL_NAME)

    return profiles


def route_incidents(
    triage_decisions: Iterable[TriageDecision],
    incidents_by_id: Mapping[str, Incident],
    *,
    strategy_name: str = "Balanced AMD Router",
    current_benchmark: Optional[AmdBenchmarkSummary] = None,
    small_model_benchmark: Optional[AmdBenchmarkSummary] = None,
    owners: Optional[Mapping[str, Mapping[str, str]]] = None,
) -> list[ModelRouteDecision]:
    """Compile triage decisions into a deterministic execution plan."""
    profiles = build_model_profiles(current_benchmark, small_model_benchmark)
    owner_directory = owners or load_owner_directory()
    routes: list[ModelRouteDecision] = []

    for decision in triage_decisions:
        incident = incidents_by_id.get(decision.incident_id)
        flag_codes = {flag.code for flag in decision.risk_flags}
        owner = get_owner_for_system(decision.system, owner_directory)

        if "HALLUCINATION_RISK" in flag_codes:
            route = _build_route(
                decision,
                owner,
                risk_tier="critical",
                selected_execution_mode="human_review",
                recommended_model=LARGE_MODEL_NAME,
                reason="Hallucination risk requires Qwen 7B critique before human approval.",
                profile=profiles["large_model"],
                include_human_review=True,
            )
        elif "SECURITY_WITHOUT_EVIDENCE" in flag_codes:
            route = _build_route(
                decision,
                owner,
                risk_tier="critical",
                selected_execution_mode="human_review",
                recommended_model="Human review packet only",
                reason="Security incident lacks evidence, so the system escalates directly to a human owner without model generation.",
                profile=profiles["deterministic_only"],
                include_human_review=True,
            )
        elif decision.trust_score < 50:
            route = _build_route(
                decision,
                owner,
                risk_tier="critical",
                selected_execution_mode="human_review",
                recommended_model="Human review packet only",
                reason="Trust score below 50 blocks autonomous narrative and requires direct human ownership without model generation.",
                profile=profiles["deterministic_only"],
                include_human_review=True,
            )
        elif decision.priority_score >= 85:
            route = _build_route(
                decision,
                owner,
                risk_tier="critical",
                selected_execution_mode="human_review",
                recommended_model=LARGE_MODEL_NAME,
                reason="Priority score above 85 routes through Qwen 7B summary and human review.",
                profile=profiles["large_model"],
                include_human_review=True,
            )
        elif "AMD_GPU_INFERENCE_DEGRADATION" in flag_codes:
            route = _build_route(
                decision,
                owner,
                risk_tier="high",
                selected_execution_mode="large_model",
                recommended_model=LARGE_MODEL_NAME,
                reason="AMD/ROCm inference degradation benefits from the large-model ROCm advisor path.",
                profile=profiles["large_model"],
                include_human_review=False,
            )
        elif decision.priority_score >= 60:
            high_risk_strategy = strategy_name in {"Quality-first", "Safety-first"}
            payment_or_database = decision.system in {"payments", "database"}
            use_large_model = high_risk_strategy or (
                strategy_name == "Balanced AMD Router" and payment_or_database
            )
            profile_key = "large_model" if use_large_model else "small_model"
            recommended_model = LARGE_MODEL_NAME if use_large_model else SMALL_MODEL_NAME
            reason = (
                "High-priority incident uses Qwen 7B for richer reasoning under the selected strategy."
                if use_large_model
                else "High-priority incident uses the smaller model to preserve latency while keeping narrative coverage."
            )
            route = _build_route(
                decision,
                owner,
                risk_tier="high",
                selected_execution_mode="large_model" if use_large_model else "small_model",
                recommended_model=recommended_model,
                reason=reason,
                profile=profiles[profile_key],
                include_human_review=False,
            )
        elif decision.priority_score >= 45:
            route = _build_route(
                decision,
                owner,
                risk_tier="medium",
                selected_execution_mode="small_model",
                recommended_model=SMALL_MODEL_NAME,
                reason="Medium-priority incident receives a smaller-model narrative summary.",
                profile=profiles["small_model"],
                include_human_review=False,
            )
        else:
            route = _build_route(
                decision,
                owner,
                risk_tier="low",
                selected_execution_mode="deterministic_only",
                recommended_model="Deterministic rules only",
                reason="Low-risk incident stays on deterministic scoring and templated actions.",
                profile=profiles["deterministic_only"],
                include_human_review=False,
            )

        if incident is not None and incident.sla_minutes_remaining <= 15:
            route.safety_notes.append(
                f"SLA window is {incident.sla_minutes_remaining} minutes; keep escalation packet ready."
            )

        routes.append(route)

    return routes


def _build_route(
    decision: TriageDecision,
    owner: Mapping[str, str],
    *,
    risk_tier: str,
    selected_execution_mode: str,
    recommended_model: str,
    reason: str,
    profile: Mapping[str, object],
    include_human_review: bool,
) -> ModelRouteDecision:
    latency_ms = float(profile["latency_ms"])
    if include_human_review and recommended_model == LARGE_MODEL_NAME:
        latency_ms = float(profile["p95_latency_ms"])

    safety_notes = [
        "Deterministic priority, confidence, trust, and risk flags remain authoritative.",
        str(profile["source"]),
    ]
    if include_human_review:
        safety_notes.append("Human response time is not included in the automated latency estimate.")
    if recommended_model == "Human review packet only":
        safety_notes.append("No model generation is required before the incident is handed to the owner.")
    if selected_execution_mode == "deterministic_only":
        safety_notes.append("Latency is a deterministic/template estimate, not model inference latency.")
    if profile.get("estimated"):
        safety_notes.append("Estimate is simulated because a verified benchmark for this path is missing.")

    return ModelRouteDecision(
        incident_id=decision.incident_id,
        title=decision.title,
        system=decision.system,
        risk_tier=risk_tier,
        selected_execution_mode=selected_execution_mode,
        recommended_model=recommended_model,
        reason=reason,
        expected_latency_ms=round(latency_ms, 2),
        expected_cost_usd=round(float(profile["cost_usd"]), 4),
        safety_notes=safety_notes,
        owner_email=owner["owner_email"],
        owner_name=owner["owner_name"],
    )


def _select_large_model_benchmark(
    current_benchmark: Optional[AmdBenchmarkSummary],
) -> Optional[AmdBenchmarkSummary]:
    if _is_verified_benchmark(current_benchmark) and current_benchmark.model == LARGE_MODEL_NAME:
        return current_benchmark

    fallback = load_benchmark_results(QWEN7B_BENCHMARK_PATH)
    if _is_verified_benchmark(fallback) and fallback.model == LARGE_MODEL_NAME:
        return fallback
    return None


def _select_small_model_benchmark(
    small_model_benchmark: Optional[AmdBenchmarkSummary],
) -> Optional[AmdBenchmarkSummary]:
    if _is_verified_benchmark(small_model_benchmark) and small_model_benchmark.model == SMALL_MODEL_NAME:
        return small_model_benchmark

    fallback = load_benchmark_results(QWEN15B_BENCHMARK_PATH)
    if _is_verified_benchmark(fallback) and fallback.model == SMALL_MODEL_NAME:
        return fallback
    return None


def _is_verified_benchmark(summary: Optional[AmdBenchmarkSummary]) -> bool:
    return bool(
        summary
        and summary.successful_requests > 0
        and summary.total_requests > 0
        and not summary.mock_mode
    )


def _benchmark_profile(summary: AmdBenchmarkSummary, model_name: str) -> Dict[str, object]:
    total_tokens = summary.estimated_total_tokens or 0
    total_requests = max(summary.total_requests, 1)
    avg_tokens_per_request = total_tokens / total_requests if total_tokens else 600.0
    rate = MODEL_RATE_USD_PER_MTOKEN.get(model_name, 1.20)
    cost_usd = (avg_tokens_per_request / 1_000_000) * rate
    return {
        "latency_ms": round(summary.p50_latency_ms or summary.avg_latency_ms, 2),
        "p95_latency_ms": round(summary.p95_latency_ms or summary.avg_latency_ms, 2),
        "cost_usd": round(cost_usd, 4),
        "source": f"Latency sourced from verified benchmark run {summary.run_id} ({summary.model})",
        "estimated": False,
    }
