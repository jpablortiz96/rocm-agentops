"""Throughput degradation detector."""

from __future__ import annotations

from typing import Any, Dict, List


def detect_throughput_incidents(
    benchmark_data: Dict[str, Any],
    *,
    minimum_tokens_per_second: float,
) -> List[Dict[str, Any]]:
    """Generate incidents when throughput degrades below the configured threshold."""
    summary = benchmark_data.get("summary") or {}
    tokens_per_second = summary.get("tokens_per_second")
    if tokens_per_second is None or tokens_per_second >= minimum_tokens_per_second:
        return []

    return [
        {
            "kind": "throughput_degradation",
            "title": "AMD-backed inference throughput degradation",
            "description": (
                f"Estimated throughput dropped to {tokens_per_second:.2f} tokens/sec, "
                f"below the configured threshold of {minimum_tokens_per_second:.0f}."
            ),
            "system": "inference",
            "severity_hint": "high",
            "status": "investigating",
            "location": "amd-live-endpoint",
            "affected_users": 600,
            "revenue_impact_usd": 6000,
            "sla_minutes_remaining": 35,
            "evidence": [
                f"Benchmark run {summary.get('run_id', 'unknown')}",
                f"Tokens/sec: {tokens_per_second:.2f}",
                f"Concurrency levels: {summary.get('concurrency_levels')}",
            ],
        }
    ]
