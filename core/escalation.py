"""Owner-aware escalation packet generation."""

from __future__ import annotations

from typing import Iterable, Mapping, Optional

from core.benchmark_schemas import AmdBenchmarkSummary
from core.model_router import get_owner_for_system, load_owner_directory
from core.schemas import EscalationPacket, Incident, TriageDecision


def generate_escalation_packets(
    triage_decisions: Iterable[TriageDecision],
    incidents_by_id: Mapping[str, Incident],
    *,
    run_id: str,
    audit_id: str,
    benchmark_summary: Optional[AmdBenchmarkSummary] = None,
    llm_runtime_info: Optional[dict] = None,
    owners: Optional[Mapping[str, Mapping[str, str]]] = None,
    incident_policy_hits: Optional[Mapping[str, list[str]]] = None,
) -> list[EscalationPacket]:
    """Build markdown and EML handoff packets for incidents needing human review."""
    owner_directory = owners or load_owner_directory()
    runtime_info = llm_runtime_info or {}
    policy_hits_map = incident_policy_hits or {}
    packets: list[EscalationPacket] = []

    for decision in triage_decisions:
        if not decision.human_review_required:
            continue

        incident = incidents_by_id.get(decision.incident_id)
        owner = get_owner_for_system(decision.system, owner_directory)
        risk_labels = [f"{flag.label} ({flag.severity})" for flag in decision.risk_flags]
        evidence = incident.evidence if incident else []
        severity_tag = "CRITICAL"
        subject = (
            f"[ROCm AgentOps][{severity_tag}][{decision.incident_id}] "
            f"{decision.title} - Human Review Required"
        )

        markdown_body = _build_markdown_packet(
            decision=decision,
            incident=incident,
            owner=owner,
            run_id=run_id,
            audit_id=audit_id,
            benchmark_summary=benchmark_summary,
            runtime_info=runtime_info,
            subject=subject,
            risk_labels=risk_labels,
            evidence=evidence,
            policy_hits=policy_hits_map.get(decision.incident_id, []),
        )
        eml_content = _build_eml_packet(
            recipient_name=owner["owner_name"],
            recipient_email=owner["owner_email"],
            subject=subject,
            body_markdown=markdown_body,
        )

        packets.append(
            EscalationPacket(
                incident_id=decision.incident_id,
                recipient_name=owner["owner_name"],
                recipient_email=owner["owner_email"],
                slack_channel=owner["slack_channel"],
                subject=subject,
                markdown_body=markdown_body,
                eml_content=eml_content,
                priority_score=decision.priority_score,
                trust_score=decision.trust_score,
                risk_flags=risk_labels,
                recommended_action=decision.recommended_action,
                sla_minutes_remaining=incident.sla_minutes_remaining if incident else None,
                run_id=run_id,
                audit_id=audit_id,
                benchmark_run_id=benchmark_summary.run_id if benchmark_summary else "",
                policy_hits=policy_hits_map.get(decision.incident_id, []),
            )
        )

    return packets


def _build_markdown_packet(
    *,
    decision: TriageDecision,
    incident: Optional[Incident],
    owner: Mapping[str, str],
    run_id: str,
    audit_id: str,
    benchmark_summary: Optional[AmdBenchmarkSummary],
    runtime_info: Mapping[str, object],
    subject: str,
    risk_labels: list[str],
    evidence: list[str],
    policy_hits: list[str],
) -> str:
    runtime_mode = runtime_info.get("narrative_mode", "Unknown")
    model_name = runtime_info.get("model", "Unknown")
    fallback_count = len(runtime_info.get("errors", []))
    benchmark_run_id = benchmark_summary.run_id if benchmark_summary else "N/A"
    benchmark_model = benchmark_summary.model if benchmark_summary else "N/A"
    benchmark_success = (
        f"{benchmark_summary.successful_requests}/{benchmark_summary.total_requests}"
        if benchmark_summary
        else "N/A"
    )
    evidence_lines = "\n".join(f"- {item}" for item in evidence) if evidence else "- No evidence attached"
    risk_lines = "\n".join(f"- {label}" for label in risk_labels) if risk_labels else "- No explicit risk flags"
    reasons = "\n".join(f"- {reason}" for reason in decision.reasons[:4])
    policy_lines = "\n".join(f"- {policy_id}" for policy_id in policy_hits) if policy_hits else "- No explicit policy hits recorded"

    return "\n".join(
        [
            f"# {subject}",
            "",
            "## Executive Summary",
            (
                f"{decision.incident_id} was escalated to {owner['owner_name']} because the deterministic "
                f"workflow marked it as high-risk with a trust score of {decision.trust_score:.1f}."
            ),
            "",
            "## Why This Was Escalated",
            reasons or "- Deterministic policy triggered a human review gate.",
            "",
            "## Evidence",
            evidence_lines,
            "",
            "## Risk Flags",
            risk_lines,
            "",
            "## Policy Guardrails",
            policy_lines,
            "",
            "## Recommended Next Action",
            f"- {decision.recommended_action}",
            f"- Slack channel: {owner['slack_channel']}",
            "",
            "## Trace and Audit",
            f"- Run ID: {run_id}",
            f"- Audit Seal ID: {audit_id}",
            f"- Recipient: {owner['owner_email']}",
            "",
            "## AMD Runtime Summary",
            f"- Narrative mode: {runtime_mode}",
            f"- Active model: {model_name}",
            f"- Benchmark run ID: {benchmark_run_id}",
            f"- Benchmark model: {benchmark_model}",
            f"- Benchmark success: {benchmark_success}",
            f"- Fallback count: {fallback_count}",
            "",
            "## Incident Snapshot",
            f"- Priority score: {decision.priority_score:.1f}",
            f"- Trust score: {decision.trust_score:.1f}",
            f"- System: {decision.system}",
            f"- SLA remaining: {incident.sla_minutes_remaining if incident else 'N/A'} minutes",
            "",
            "Generated by ROCm AgentOps; human validation required.",
        ]
    )


def _build_eml_packet(
    *,
    recipient_name: str,
    recipient_email: str,
    subject: str,
    body_markdown: str,
) -> str:
    return "\n".join(
        [
            "From: ROCm AgentOps <no-reply@example.com>",
            f"To: {recipient_name} <{recipient_email}>",
            f"Subject: {subject}",
            "MIME-Version: 1.0",
            "Content-Type: text/plain; charset=utf-8",
            "",
            body_markdown,
            "",
        ]
    )
