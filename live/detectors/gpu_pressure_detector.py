"""GPU telemetry pressure detector."""

from __future__ import annotations

from typing import Any, Dict, List


def detect_gpu_pressure_incidents(
    gpu_metrics: Dict[str, Any],
    *,
    util_threshold_pct: float,
    memory_threshold_pct: float,
) -> List[Dict[str, Any]]:
    """Generate incidents from GPU pressure metrics."""
    if not gpu_metrics.get("available"):
        return []

    findings: List[Dict[str, Any]] = []
    utilization = gpu_metrics.get("utilization_pct")
    memory_usage = gpu_metrics.get("memory_usage_pct")
    temp_c = gpu_metrics.get("temperature_c")

    if memory_usage is not None and memory_usage >= memory_threshold_pct:
        findings.append(
            {
                "kind": "gpu_memory_pressure",
                "title": "AMD GPU memory pressure detected",
                "description": f"Observed GPU memory usage of {memory_usage:.1f}% from ROCm telemetry.",
                "system": "inference",
                "severity_hint": "high",
                "status": "investigating",
                "location": "rocm-smi",
                "affected_users": 400,
                "revenue_impact_usd": 5000,
                "sla_minutes_remaining": 30,
                "evidence": [
                    f"GPU memory usage: {memory_usage:.1f}%",
                    f"Utilization: {utilization if utilization is not None else 'N/A'}",
                ],
            }
        )

    if utilization is not None and utilization >= util_threshold_pct:
        findings.append(
            {
                "kind": "gpu_utilization_pressure",
                "title": "Sustained AMD GPU utilization pressure",
                "description": f"ROCm telemetry reported GPU utilization of {utilization:.1f}%.",
                "system": "inference",
                "severity_hint": "medium",
                "status": "investigating",
                "location": "rocm-smi",
                "affected_users": 250,
                "revenue_impact_usd": 2500,
                "sla_minutes_remaining": 45,
                "evidence": [
                    f"GPU utilization: {utilization:.1f}%",
                    f"Temperature: {temp_c if temp_c is not None else 'N/A'}",
                ],
            }
        )
    return findings
