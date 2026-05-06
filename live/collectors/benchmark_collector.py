"""Benchmark summary collector for live signal intake."""

from __future__ import annotations

from typing import Any, Dict

from core.benchmarking import load_benchmark_results


def collect_benchmark_summary(path: str = "data/amd_benchmark_results.json") -> Dict[str, Any]:
    """Read benchmark results from disk when available."""
    summary = load_benchmark_results(path)
    if summary is None:
        return {"available": False, "summary": None, "errors": []}

    failed_requests = [
        {
            "request_id": result.request_id,
            "error": result.error,
            "latency_ms": result.latency_ms,
        }
        for result in summary.request_results
        if not result.success
    ]
    return {
        "available": True,
        "summary": {
            "run_id": summary.run_id,
            "successful_requests": summary.successful_requests,
            "failed_requests": summary.failed_requests,
            "total_requests": summary.total_requests,
            "success_rate": (
                float(summary.successful_requests) / float(summary.total_requests)
                if summary.total_requests
                else 0.0
            ),
            "avg_latency_ms": summary.avg_latency_ms,
            "p50_latency_ms": summary.p50_latency_ms,
            "p95_latency_ms": summary.p95_latency_ms,
            "tokens_per_second": summary.estimated_tokens_per_second,
            "concurrency_levels": summary.concurrency_levels,
            "model": summary.model,
            "mock_mode": summary.mock_mode,
        },
        "errors": failed_requests,
        "raw": summary,
    }
