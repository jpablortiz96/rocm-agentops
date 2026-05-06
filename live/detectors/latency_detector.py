"""Latency signal detector."""

from __future__ import annotations

from typing import Any, Dict, List


def detect_latency_incidents(
    benchmark_data: Dict[str, Any],
    endpoint_probe: Dict[str, Any],
    *,
    p95_threshold_ms: float,
) -> List[Dict[str, Any]]:
    """Generate incidents from latency breach signals."""
    findings: List[Dict[str, Any]] = []
    summary = benchmark_data.get("summary") or {}
    p95_latency = summary.get("p95_latency_ms")
    if p95_latency is not None and p95_latency >= p95_threshold_ms:
        findings.append(
            {
                "kind": "latency_breach",
                "title": "Inference p95 latency breach on AMD-backed endpoint",
                "description": (
                    f"Benchmark p95 latency reached {p95_latency:.2f} ms, meeting or exceeding "
                    f"the configured threshold of {p95_threshold_ms:.0f} ms."
                ),
                "system": "inference",
                "severity_hint": "high" if p95_latency < p95_threshold_ms * 1.2 else "critical",
                "status": "investigating",
                "location": "amd-live-endpoint",
                "affected_users": 1200,
                "revenue_impact_usd": 15000,
                "sla_minutes_remaining": 20,
                "evidence": [
                    f"Benchmark run {summary.get('run_id', 'unknown')}",
                    f"p95 latency: {p95_latency:.2f} ms",
                    f"Average latency: {summary.get('avg_latency_ms', 'N/A')}",
                ],
            }
        )

    probe_latency = endpoint_probe.get("latency_ms")
    if endpoint_probe.get("chat_success") and probe_latency and probe_latency >= p95_threshold_ms * 0.75:
        findings.append(
            {
                "kind": "probe_latency_warning",
                "title": "Live endpoint response latency elevated",
                "description": (
                    f"Endpoint probe chat completion took {probe_latency:.2f} ms, indicating elevated live runtime latency."
                ),
                "system": "inference",
                "severity_hint": "medium",
                "status": "investigating",
                "location": "amd-live-endpoint",
                "affected_users": 250,
                "revenue_impact_usd": 2500,
                "sla_minutes_remaining": 45,
                "evidence": [
                    f"Endpoint probe latency: {probe_latency:.2f} ms",
                    f"Endpoint health: {endpoint_probe.get('endpoint_health')}",
                ],
            }
        )
    return findings
