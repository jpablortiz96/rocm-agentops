"""Build-in-public telemetry card generation."""

from __future__ import annotations

from typing import Iterable, Optional

from core.benchmark_schemas import AmdBenchmarkSummary
from core.schemas import ModelRouteDecision, TelemetryCard, TriageDecision

DEFAULT_HASHTAGS = [
    "#ROCm",
    "#AMDDeveloperCloud",
    "#AIatAMD",
    "#AgentOps",
    "#OpenSourceAI",
]


def generate_telemetry_card(
    *,
    workflow_run_id: str,
    benchmark_summary: Optional[AmdBenchmarkSummary],
    llm_runtime_info: dict,
    triage_decisions: Iterable[TriageDecision],
    model_routes: Iterable[ModelRouteDecision],
    mismatch_insights: list[str],
) -> TelemetryCard:
    """Generate a markdown card suitable for sharing benchmark-backed progress."""
    decisions = list(triage_decisions)
    routes = list(model_routes)
    fallback_count = len(llm_runtime_info.get("errors", []))
    top_agentops_insight = _top_agentops_insight(decisions, routes)
    mismatch_insight = _clean_markdown(mismatch_insights[0]) if mismatch_insights else (
        "Baseline and AgentOps remained aligned on the most important incidents."
    )

    if benchmark_summary is not None and benchmark_summary.total_requests:
        success_rate = benchmark_summary.successful_requests / benchmark_summary.total_requests
        benchmark_run_id = benchmark_summary.run_id
        model_name = benchmark_summary.model
        p50_latency_ms = benchmark_summary.p50_latency_ms
        p95_latency_ms = benchmark_summary.p95_latency_ms
        tokens_per_second = benchmark_summary.estimated_tokens_per_second
        successful_requests = benchmark_summary.successful_requests
        failed_requests = benchmark_summary.failed_requests
    else:
        success_rate = 0.0
        benchmark_run_id = "unverified"
        model_name = llm_runtime_info.get("model", "Unknown")
        p50_latency_ms = 0.0
        p95_latency_ms = 0.0
        tokens_per_second = 0.0
        successful_requests = 0
        failed_requests = 0

    markdown = "\n".join(
        [
            "# ROCm AgentOps AMD Run",
            "",
            f"- Workflow run ID: {workflow_run_id}",
            f"- Model: {model_name}",
            "- Endpoint type: OpenAI-compatible AMD/vLLM endpoint",
            f"- Benchmark run ID: {benchmark_run_id}",
            f"- Successful requests: {successful_requests}",
            f"- Failed requests: {failed_requests}",
            f"- p50 latency: {p50_latency_ms:.2f} ms",
            f"- p95 latency: {p95_latency_ms:.2f} ms",
            f"- Estimated tokens/sec: {tokens_per_second:.2f}",
            f"- Fallback count: {fallback_count}",
            f"- Top AgentOps insight: {top_agentops_insight}",
            f"- Baseline mismatch insight: {mismatch_insight}",
            "- Note: deterministic scoring stays local while Qwen 7B narrative and critique run on AMD/vLLM when the workflow needs deeper reasoning.",
        ]
    )
    suggested_post_text = _build_suggested_post(
        benchmark_run_id=benchmark_run_id,
        successful_requests=successful_requests,
        failed_requests=failed_requests,
        p95_latency_ms=p95_latency_ms,
        top_agentops_insight=top_agentops_insight,
        mismatch_insight=mismatch_insight,
    )

    return TelemetryCard(
        title="ROCm AgentOps AMD Run",
        markdown=markdown,
        suggested_post_text=suggested_post_text,
        hashtags=DEFAULT_HASHTAGS,
        workflow_run_id=workflow_run_id,
        benchmark_run_id=benchmark_run_id,
        model=model_name,
        success_rate=round(success_rate, 4),
        p50_latency_ms=round(p50_latency_ms, 2),
        p95_latency_ms=round(p95_latency_ms, 2),
        tokens_per_second=round(tokens_per_second, 2),
    )


def _top_agentops_insight(
    decisions: list[TriageDecision],
    routes: list[ModelRouteDecision],
) -> str:
    flag_codes_by_incident = {
        decision.incident_id: {flag.code for flag in decision.risk_flags}
        for decision in decisions
    }
    route_map = {route.incident_id: route for route in routes}

    if "INC-004" in route_map and "SECURITY_WITHOUT_EVIDENCE" in flag_codes_by_incident.get("INC-004", set()):
        return (
            "AgentOps escalated the low-trust security incident INC-004 directly to human review "
            "instead of treating low user count as a sign of low business impact."
        )

    if "INC-007" in route_map and "HALLUCINATION_RISK" in flag_codes_by_incident.get("INC-007", set()):
        return (
            "AgentOps recognizes hallucination as an operational risk and compiles INC-007 into "
            "Qwen 7B critique plus human review."
        )

    low_risk_det = [route.incident_id for route in routes if route.selected_execution_mode == "deterministic_only"]
    if low_risk_det:
        return (
            f"AgentOps kept {', '.join(low_risk_det[:2])} on deterministic execution to preserve cost and latency budget."
        )

    return "AgentOps used deterministic scoring first, then selectively escalated only the risky narratives."


def _clean_markdown(value: str) -> str:
    return value.replace("**", "").replace("`", "")


def _build_suggested_post(
    *,
    benchmark_run_id: str,
    successful_requests: int,
    failed_requests: int,
    p95_latency_ms: float,
    top_agentops_insight: str,
    mismatch_insight: str,
) -> str:
    hashtags = " ".join(DEFAULT_HASHTAGS)
    post = (
        "ROCm AgentOps now compiles agentic incident response into deterministic, Qwen 1.5B, "
        "Qwen 7B, and human-review paths using verified AMD/vLLM evidence. "
        f"Latest AMD run {benchmark_run_id}: {successful_requests}/{successful_requests + failed_requests} "
        f"successful requests, {p95_latency_ms:.0f} ms p95 latency. "
        f"{top_agentops_insight} {mismatch_insight} {hashtags}"
    )
    if len(post) <= 900:
        return post

    reserved = len(hashtags) + 1
    body = (
        "ROCm AgentOps now compiles agentic incident response into deterministic, Qwen 1.5B, "
        "Qwen 7B, and human-review paths using verified AMD/vLLM evidence. "
        f"Latest AMD run {benchmark_run_id}: {successful_requests}/{successful_requests + failed_requests} "
        f"successful requests, {p95_latency_ms:.0f} ms p95 latency. "
        f"{top_agentops_insight} {mismatch_insight}"
    )
    truncated_body = body[: max(0, 900 - reserved - 3)].rstrip()
    return f"{truncated_body}... {hashtags}"
