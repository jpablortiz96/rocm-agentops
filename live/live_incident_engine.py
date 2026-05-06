"""Generate incidents from live workload evidence captured from AMD-backed infrastructure."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from core.config import config
from live.collectors.benchmark_collector import collect_benchmark_summary
from live.collectors.endpoint_probe import probe_endpoint
from live.collectors.gpu_metrics_collector import collect_gpu_metrics
from live.collectors.log_collector import collect_logs
from live.normalizers.incident_normalizer import normalize_live_findings


@dataclass
class LiveIncidentRun:
    incidents: list
    signal_summary: Dict[str, Any]


def generate_live_incidents(
    *,
    base_url: str,
    model: str,
    api_key: str,
    mock_mode: bool,
    enable_live_endpoint_probe: bool,
    thresholds: Dict[str, float],
) -> LiveIncidentRun:
    """Collect runtime signals, evaluate thresholds, and normalize incidents."""
    endpoint = (
        probe_endpoint(
            base_url=base_url,
            model=model,
            api_key=api_key,
            timeout=config.LIVE_SIGNAL_TIMEOUT,
        )
        if enable_live_endpoint_probe
        else _build_skipped_probe_result(base_url=base_url, model=model)
    )
    benchmark = collect_benchmark_summary()
    gpu_metrics = collect_gpu_metrics(timeout=config.LIVE_SIGNAL_TIMEOUT)
    log_paths = [path for path in config.LIVE_LOG_PATHS.split(";") if path.strip()]
    logs = collect_logs(log_paths)

    findings = _build_signal_findings(
        endpoint=endpoint,
        benchmark=benchmark,
        gpu_metrics=gpu_metrics,
        logs=logs,
        base_url=base_url,
        thresholds=thresholds,
    )
    incidents = normalize_live_findings(_build_live_incidents(endpoint, benchmark, gpu_metrics, thresholds))

    no_incident_reason = ""
    if not incidents:
        no_incident_reason = (
            "No live incidents generated because all signals are within thresholds. "
            "Adjust SLA threshold or use Hybrid mode for demo."
        )

    signal_summary = {
        "live_evidence_enabled": True,
        "endpoint_health": _derive_endpoint_health(endpoint),
        "endpoint_available": endpoint.get("endpoint_available", False),
        "benchmark_available": benchmark.get("available", False),
        "gpu_telemetry_available": gpu_metrics.get("available", False),
        "logs_available": logs.get("available", False),
        "live_incidents_generated": len(incidents),
        "findings": findings,
        "no_incident_reason": no_incident_reason,
        "thresholds": thresholds,
        "details": {
            "endpoint": endpoint,
            "benchmark": benchmark.get("summary"),
            "gpu_metrics": gpu_metrics,
            "logs": {
                "available": logs.get("available", False),
                "missing_paths": logs.get("missing_paths", []),
                "reason": logs.get("reason"),
            },
            "runtime_context": {
                "mock_mode": mock_mode,
                "enable_live_endpoint_probe": enable_live_endpoint_probe,
                "base_url": base_url,
                "model": model,
            },
        },
    }
    return LiveIncidentRun(incidents=incidents, signal_summary=signal_summary)


def _build_signal_findings(
    *,
    endpoint: Dict[str, Any],
    benchmark: Dict[str, Any],
    gpu_metrics: Dict[str, Any],
    logs: Dict[str, Any],
    base_url: str,
    thresholds: Dict[str, float],
) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    summary = benchmark.get("summary") or {}
    endpoint_health = _derive_endpoint_health(endpoint)

    findings.append(
        {
            "label": "endpoint online/offline",
            "status": _status_for_endpoint(endpoint_health),
            "severity": _severity_for_endpoint(endpoint_health),
            "summary": _endpoint_summary(endpoint),
            "evidence": [
                f"Model: {endpoint.get('model', 'N/A')}",
                f"Base URL: {endpoint.get('base_url', base_url)}",
                f"Status code: {endpoint.get('status_code') or endpoint.get('models_status_code') or 'N/A'}",
                f"Probe latency: {endpoint.get('latency_ms') or 'N/A'} ms",
                f"Probe response: {endpoint.get('probe_response_preview') or 'N/A'}",
            ],
        }
    )
    findings.append(
        {
            "label": "benchmark available yes/no",
            "status": "pass" if benchmark.get("available") else "warn",
            "severity": "low",
            "summary": "Benchmark artifacts detected." if benchmark.get("available") else "Benchmark artifacts not available.",
            "evidence": [f"Benchmark run ID: {summary.get('run_id', 'N/A')}"],
        }
    )

    p95_threshold = float(thresholds["p95_latency_sla_ms"])
    warning_threshold = p95_threshold * float(thresholds["warning_threshold_pct"])
    if benchmark.get("available"):
        p95_latency = float(summary.get("p95_latency_ms") or 0.0)
        if p95_latency >= p95_threshold:
            p95_status = "fail"
            p95_severity = "high"
            p95_summary = "p95 latency breached SLA."
        elif p95_latency >= warning_threshold:
            p95_status = "warn"
            p95_severity = "warning"
            p95_summary = "p95 latency near SLA limit."
        else:
            p95_status = "pass"
            p95_severity = "low"
            p95_summary = "p95 latency within SLA."
        p95_evidence = [
            f"Benchmark p95 latency: {p95_latency:.2f} ms",
            f"Configured p95 SLA: {p95_threshold:.2f} ms",
            f"Warning threshold: {warning_threshold:.2f} ms",
        ]
        success_rate = float(summary.get("success_rate") or 0.0)
        success_rate_summary = f"Benchmark success rate: {success_rate:.1%}"
        success_status = "pass" if success_rate >= float(thresholds["minimum_success_rate"]) else "fail"
        success_severity = "low" if success_rate >= float(thresholds["minimum_success_rate"]) else "high"
        failed_request_count = int(summary.get("failed_requests", 0))
        failed_requests_summary = f"Failed requests: {failed_request_count}"
        failed_requests_status = "pass" if failed_request_count <= int(thresholds["max_failed_requests"]) else "fail"
        failed_requests_severity = "low" if failed_request_count <= int(thresholds["max_failed_requests"]) else "high"
    else:
        p95_status = "warn"
        p95_severity = "warning"
        p95_summary = "p95 latency status unavailable because no benchmark artifact was found."
        p95_evidence = [
            f"Configured p95 SLA: {p95_threshold:.2f} ms",
            f"Warning threshold: {warning_threshold:.2f} ms",
        ]
        success_rate_summary = "Benchmark success rate unavailable."
        success_status = "warn"
        success_severity = "warning"
        failed_requests_summary = "Failed request count unavailable."
        failed_requests_status = "warn"
        failed_requests_severity = "warning"

    findings.append(
        {
            "label": "p95 latency status",
            "status": p95_status,
            "severity": p95_severity,
            "summary": p95_summary,
            "evidence": p95_evidence,
        }
    )
    findings.append(
        {
            "label": "success rate",
            "status": success_status,
            "severity": success_severity,
            "summary": success_rate_summary,
            "evidence": [
                f"Successful requests: {summary.get('successful_requests', 'N/A')}",
                f"Failed requests: {summary.get('failed_requests', 'N/A')}",
            ],
        }
    )
    findings.append(
        {
            "label": "failed requests",
            "status": failed_requests_status,
            "severity": failed_requests_severity,
            "summary": failed_requests_summary,
            "evidence": [
                f"Allowed failed requests: {thresholds['max_failed_requests']}",
                f"Benchmark run ID: {summary.get('run_id', 'N/A')}",
            ],
        }
    )

    findings.append(
        {
            "label": "GPU telemetry available yes/no",
            "status": "pass" if gpu_metrics.get("available") else "warn",
            "severity": "low",
            "summary": "GPU telemetry available." if gpu_metrics.get("available") else "GPU telemetry unavailable.",
            "evidence": [
                f"Source: {gpu_metrics.get('source', 'N/A')}",
                f"Reason: {gpu_metrics.get('reason', 'N/A')}",
            ],
        }
    )
    if gpu_metrics.get("available"):
        util = gpu_metrics.get("utilization_pct")
        memory_pct = gpu_metrics.get("memory_usage_pct")
        if util is not None:
            findings.append(
                {
                    "label": "gpu utilization",
                    "status": "info" if float(util) == 0.0 else "warn" if float(util) >= 95.0 else "pass",
                    "severity": "info" if float(util) == 0.0 else "warning" if float(util) >= 95.0 else "low",
                    "summary": (
                        "GPU utilization is currently idle or in a low-power state."
                        if float(util) == 0.0
                        else
                        f"GPU utilization elevated at {float(util):.1f}%."
                        if float(util) >= 95.0
                        else f"GPU utilization normal at {float(util):.1f}%."
                    ),
                    "evidence": [
                        f"Duration seconds: {gpu_metrics.get('duration_seconds', 'N/A')}",
                        f"Telemetry source: {gpu_metrics.get('source', 'N/A')}",
                    ],
                }
            )
        if memory_pct is not None:
            findings.append(
                {
                    "label": "gpu memory pressure",
                    "status": "fail" if float(memory_pct) >= 90.0 else "warn" if float(memory_pct) >= 80.0 else "pass",
                    "severity": "high" if float(memory_pct) >= 90.0 else "warning" if float(memory_pct) >= 80.0 else "low",
                    "summary": (
                        f"GPU memory pressure critical at {float(memory_pct):.1f}%."
                        if float(memory_pct) >= 90.0
                        else f"GPU memory pressure near threshold at {float(memory_pct):.1f}%."
                        if float(memory_pct) >= 80.0
                        else f"GPU memory usage normal at {float(memory_pct):.1f}%."
                    ),
                    "evidence": [
                        f"Temperature: {gpu_metrics.get('temperature_c', 'N/A')}",
                        f"Power: {gpu_metrics.get('power_w', 'N/A')}",
                        f"Telemetry source: {gpu_metrics.get('source', 'N/A')}",
                    ],
                }
            )
    findings.append(
        {
            "label": "logs available yes/no",
            "status": "pass" if logs.get("available") else "warn",
            "severity": "low",
            "summary": "Log sources available." if logs.get("available") else "Log sources unavailable or not configured.",
            "evidence": [
                f"Missing paths: {', '.join(logs.get('missing_paths', [])) or 'None'}",
                f"Reason: {logs.get('reason', 'N/A')}",
            ],
        }
    )
    return findings


def _build_live_incidents(
    endpoint: Dict[str, Any],
    benchmark: Dict[str, Any],
    gpu_metrics: Dict[str, Any],
    thresholds: Dict[str, float],
) -> List[Dict[str, Any]]:
    incidents: List[Dict[str, Any]] = []
    summary = benchmark.get("summary") or {}

    if _derive_endpoint_health(endpoint) == "unavailable":
        incidents.append(
            {
                "id": "INC-LIVE-ENDPOINT-DOWN",
                "title": "AMD/vLLM inference endpoint unavailable",
                "description": "The configured OpenAI-compatible endpoint did not respond successfully during live probing.",
                "system": "inference",
                "severity_hint": "critical",
                "status": "open",
                "location": "amd-developer-cloud",
                "affected_users": 2000,
                "revenue_impact_usd": 18000,
                "sla_minutes_remaining": 10,
                "evidence": [
                    f"Endpoint available: {endpoint.get('endpoint_available')}",
                    f"Status code: {endpoint.get('status_code') or endpoint.get('models_status_code') or 'N/A'}",
                    f"Probe error: {endpoint.get('error') or 'Unknown'}",
                ],
                "source": "amd_live_signals",
            }
        )

    if benchmark.get("available"):
        p95_threshold = float(thresholds["p95_latency_sla_ms"])
        p95_latency = float(summary.get("p95_latency_ms") or 0.0)
        if p95_latency >= p95_threshold:
            incidents.append(
                {
                    "id": "INC-LIVE-LATENCY",
                    "title": "Qwen 7B endpoint p95 latency breached SLA",
                    "description": "Benchmark evidence indicates the AMD-backed Qwen 7B endpoint exceeded the configured p95 latency SLA.",
                    "system": "inference",
                    "severity_hint": "high",
                    "status": "open",
                    "location": "amd-developer-cloud",
                    "affected_users": 1200,
                    "revenue_impact_usd": 15000,
                    "sla_minutes_remaining": 20,
                    "evidence": [
                        f"Benchmark p95 latency: {p95_latency:.2f} ms",
                        f"Configured p95 SLA: {p95_threshold:.2f} ms",
                        f"Benchmark run ID: {summary.get('run_id', 'N/A')}",
                        f"Model: {summary.get('model', 'N/A')}",
                    ],
                    "source": "amd_live_signals",
                }
            )

        failed_requests = int(summary.get("failed_requests") or 0)
        if failed_requests > int(thresholds["max_failed_requests"]):
            incidents.append(
                {
                    "id": "INC-LIVE-BENCHMARK-FAILURES",
                    "title": "Benchmark failures detected on AMD/vLLM endpoint",
                    "description": "The latest benchmark produced more failed requests than the configured threshold allows.",
                    "system": "inference",
                    "severity_hint": "high",
                    "status": "open",
                    "location": "amd-developer-cloud",
                    "affected_users": 900,
                    "revenue_impact_usd": 9000,
                    "sla_minutes_remaining": 25,
                    "evidence": [
                        f"Failed requests: {failed_requests}",
                        f"Allowed failed requests: {int(thresholds['max_failed_requests'])}",
                        f"Benchmark run ID: {summary.get('run_id', 'N/A')}",
                        f"Model: {summary.get('model', 'N/A')}",
                    ],
                    "source": "amd_live_signals",
                }
            )

        success_rate = float(summary.get("success_rate") or 0.0)
        if success_rate < float(thresholds["minimum_success_rate"]):
            incidents.append(
                {
                    "id": "INC-LIVE-RELIABILITY",
                    "title": "Benchmark reliability below threshold",
                    "description": "The latest benchmark success rate is below the configured minimum for autonomous confidence.",
                    "system": "inference",
                    "severity_hint": "high",
                    "status": "open",
                    "location": "amd-developer-cloud",
                    "affected_users": 850,
                    "revenue_impact_usd": 8500,
                    "sla_minutes_remaining": 30,
                    "evidence": [
                        f"Benchmark success rate: {success_rate:.1%}",
                        f"Minimum required success rate: {float(thresholds['minimum_success_rate']):.1%}",
                        f"Benchmark run ID: {summary.get('run_id', 'N/A')}",
                    ],
                    "source": "amd_live_signals",
                }
            )

    memory_usage_pct = gpu_metrics.get("memory_usage_pct")
    if gpu_metrics.get("available") and memory_usage_pct is not None and float(memory_usage_pct) >= 90.0:
        incidents.append(
            {
                "id": "INC-LIVE-GPU-MEMORY",
                "title": "AMD GPU memory pressure detected",
                "description": "Optional ROCm/GPU telemetry indicates memory pressure on the inference node.",
                "system": "inference",
                "severity_hint": "high",
                "status": "open",
                "location": gpu_metrics.get("node_name") or "amd-developer-cloud",
                "affected_users": 400,
                "revenue_impact_usd": 5000,
                "sla_minutes_remaining": 30,
                "evidence": [
                    f"GPU memory usage: {float(memory_usage_pct):.1f}%",
                    f"GPU utilization: {gpu_metrics.get('utilization_pct', 'N/A')}",
                    f"Captured at: {gpu_metrics.get('captured_at', 'N/A')}",
                ],
                "source": "amd_live_signals",
            }
        )

    utilization_pct = gpu_metrics.get("utilization_pct")
    duration_seconds = gpu_metrics.get("duration_seconds")
    if (
        gpu_metrics.get("available")
        and utilization_pct is not None
        and float(utilization_pct) >= 95.0
        and duration_seconds is not None
        and float(duration_seconds) >= 300.0
    ):
        incidents.append(
            {
                "id": "INC-LIVE-GPU-UTILIZATION",
                "title": "Sustained AMD GPU utilization pressure",
                "description": "Optional ROCm/GPU telemetry indicates sustained high utilization on the inference node.",
                "system": "inference",
                "severity_hint": "medium",
                "status": "open",
                "location": gpu_metrics.get("node_name") or "amd-developer-cloud",
                "affected_users": 250,
                "revenue_impact_usd": 2500,
                "sla_minutes_remaining": 45,
                "evidence": [
                    f"GPU utilization: {float(utilization_pct):.1f}%",
                    f"Duration seconds: {float(duration_seconds):.1f}",
                    f"Captured at: {gpu_metrics.get('captured_at', 'N/A')}",
                ],
                "source": "amd_live_signals",
            }
        )

    return incidents


def _endpoint_summary(endpoint: Dict[str, Any]) -> str:
    endpoint_health = _derive_endpoint_health(endpoint)
    if endpoint_health == "skipped":
        return "Endpoint probe skipped by user."
    if endpoint_health == "healthy":
        return "Endpoint probe succeeded."
    if endpoint_health == "degraded":
        return "Endpoint probe reached the endpoint, but the chat probe did not fully pass."
    if endpoint_health == "unavailable":
        return "Endpoint probe failed."
    return "Endpoint status unknown."


def _build_skipped_probe_result(*, base_url: str, model: str) -> Dict[str, Any]:
    return {
        "endpoint_available": False,
        "endpoint_health": "skipped",
        "models_available": False,
        "chat_available": False,
        "status_code": None,
        "models_status_code": None,
        "latency_ms": None,
        "model": model,
        "detected_models": [],
        "error": None,
        "probe_response_preview": None,
        "base_url": base_url,
        "probe_skipped": True,
        "skip_reason": "Live endpoint probe disabled by user.",
    }


def _derive_endpoint_health(endpoint: Dict[str, Any]) -> str:
    if endpoint.get("probe_skipped"):
        return "skipped"
    if endpoint.get("chat_available"):
        return "healthy"
    return "unavailable"


def _status_for_endpoint(endpoint_health: str) -> str:
    if endpoint_health == "healthy":
        return "pass"
    if endpoint_health == "skipped":
        return "info"
    return "fail"


def _severity_for_endpoint(endpoint_health: str) -> str:
    if endpoint_health == "healthy":
        return "low"
    if endpoint_health == "skipped":
        return "info"
    return "high"
