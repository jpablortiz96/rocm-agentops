"""Normalize detector findings into Incident models."""

from __future__ import annotations

from typing import Iterable

from core.schemas import Incident


def normalize_live_findings(findings: Iterable[dict]) -> list[Incident]:
    """Convert detector findings into Incident schema objects."""
    incidents: list[Incident] = []
    seen_ids: set[str] = set()
    counter = 1
    for finding in findings:
        incident_id = finding.get("id", f"LIVE-{counter:03d}")
        if incident_id in seen_ids:
            continue
        seen_ids.add(incident_id)
        incidents.append(
            Incident(
                id=incident_id,
                title=finding.get("title", f"AMD Live Signal Incident {counter}"),
                description=finding.get("description", ""),
                severity_hint=finding.get("severity_hint", "medium"),
                status=finding.get("status", "investigating"),
                system=finding.get("system", "inference"),
                location=finding.get("location", "amd-live-endpoint"),
                evidence=finding.get("evidence", []),
                affected_users=int(finding.get("affected_users", 0)),
                revenue_impact_usd=float(finding.get("revenue_impact_usd", 0.0)),
                sla_minutes_remaining=int(finding.get("sla_minutes_remaining", 60)),
                source=finding.get("source", "amd_live_signals"),
            )
        )
        counter += 1
    return incidents
