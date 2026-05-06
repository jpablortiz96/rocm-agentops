"""Endpoint availability detector."""

from __future__ import annotations

from typing import Any, Dict, List


def detect_availability_incidents(endpoint_probe: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Generate incidents from endpoint availability failures."""
    if endpoint_probe.get("endpoint_health") != "unavailable":
        return []

    return [
        {
            "kind": "endpoint_unavailable",
            "title": "AMD-backed inference endpoint unavailable",
            "description": "The configured OpenAI-compatible endpoint is unavailable during live probing.",
            "system": "inference",
            "severity_hint": "critical",
            "status": "open",
            "location": "amd-live-endpoint",
            "affected_users": 2000,
            "revenue_impact_usd": 18000,
            "sla_minutes_remaining": 10,
            "evidence": [
                f"Probe error: {endpoint_probe.get('error')}",
                f"Models status: {endpoint_probe.get('status_code')}",
                f"Chat status: {endpoint_probe.get('chat_status_code')}",
            ],
        }
    ]
