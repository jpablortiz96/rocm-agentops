"""Failure signal detector."""

from __future__ import annotations

from typing import Any, Dict, List


ERROR_PATTERNS = ("connection refused", "timeout", "broken pipe", "reset", "oom", "model load")


def detect_failure_incidents(
    benchmark_data: Dict[str, Any],
    endpoint_probe: Dict[str, Any],
    log_data: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Generate incidents from failures and repeated runtime errors."""
    findings: List[Dict[str, Any]] = []
    summary = benchmark_data.get("summary") or {}
    failed_requests = int(summary.get("failed_requests", 0) or 0)
    if failed_requests > 0:
        findings.append(
            {
                "kind": "benchmark_failures",
                "title": "Benchmark requests failing on AMD-backed inference runtime",
                "description": f"{failed_requests} benchmark request(s) failed during the latest run.",
                "system": "inference",
                "severity_hint": "high",
                "status": "investigating",
                "location": "amd-live-endpoint",
                "affected_users": 900,
                "revenue_impact_usd": 9000,
                "sla_minutes_remaining": 25,
                "evidence": [
                    f"Benchmark run {summary.get('run_id', 'unknown')}",
                    *[
                        f"{item.get('request_id')}: {item.get('error')}"
                        for item in benchmark_data.get("errors", [])[:3]
                    ],
                ],
            }
        )

    if endpoint_probe.get("error") and endpoint_probe.get("endpoint_health") != "mock_mode":
        findings.append(
            {
                "kind": "probe_error",
                "title": "Endpoint probe failure",
                "description": "The live endpoint probe failed while checking the configured OpenAI-compatible endpoint.",
                "system": "inference",
                "severity_hint": "critical" if endpoint_probe.get("endpoint_health") == "unavailable" else "high",
                "status": "open",
                "location": "amd-live-endpoint",
                "affected_users": 1500,
                "revenue_impact_usd": 12000,
                "sla_minutes_remaining": 15,
                "evidence": [
                    f"Probe error: {endpoint_probe.get('error')}",
                    f"Models status: {endpoint_probe.get('status_code')}",
                    f"Chat status: {endpoint_probe.get('chat_status_code')}",
                ],
            }
        )

    for entry in log_data.get("entries", []):
        lower = entry.get("content", "").lower()
        matched = [pattern for pattern in ERROR_PATTERNS if pattern in lower]
        if matched:
            findings.append(
                {
                    "kind": "log_runtime_errors",
                    "title": "Runtime errors detected in inference service logs",
                    "description": "Configured logs contain connection, timeout, OOM, or model load errors.",
                    "system": "deployment",
                    "severity_hint": "high",
                    "status": "investigating",
                    "location": entry.get("path", "local-log"),
                    "affected_users": 300,
                    "revenue_impact_usd": 3000,
                    "sla_minutes_remaining": 30,
                    "evidence": [
                        f"Log source: {entry.get('path')}",
                        f"Detected patterns: {', '.join(sorted(set(matched)))}",
                    ],
                }
            )
            break
    return findings
