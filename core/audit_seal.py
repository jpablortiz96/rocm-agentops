"""Tamper-evident audit seal generation."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Optional

from core.schemas import AuditSeal


def generate_audit_seal(
    payload: dict[str, Any],
    *,
    generated_at: Optional[str] = None,
) -> AuditSeal:
    """Generate a stable SHA-256 seal for a workflow payload."""
    canonical_payload = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    sha256 = hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()
    seal_generated_at = generated_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    audit_id = f"audit-{sha256[:12]}"
    included_fields = sorted(payload.keys())
    explanation = (
        "SHA-256 seal generated over run metadata, incidents, triage decisions, trace events, "
        "benchmark summary, and runtime mode to make post-run tampering visible. "
        "This is not blockchain. It is a tamper-evident hash for operational auditability. "
        "If inputs or decisions change, the seal changes."
    )

    return AuditSeal(
        audit_id=audit_id,
        sha256=sha256,
        generated_at=seal_generated_at,
        included_fields=included_fields,
        explanation=explanation,
    )
