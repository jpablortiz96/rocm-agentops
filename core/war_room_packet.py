"""Build downloadable War Room Packet bundles for a workflow run."""

from __future__ import annotations

import csv
import io
import json
import zipfile
from typing import Optional

from core.benchmark_schemas import AmdBenchmarkSummary
from core.schemas import AgentRunResult, WarRoomPacketArtifact


def build_war_room_packet(
    report: AgentRunResult,
    *,
    benchmark_summary: Optional[AmdBenchmarkSummary] = None,
) -> WarRoomPacketArtifact:
    """Package key workflow artifacts into a ZIP handoff bundle."""
    file_name = f"rocm_agentops_war_room_{report.run_id}.zip"
    buffer = io.BytesIO()
    included_files: list[str] = []

    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        _write_text_file(
            archive,
            included_files,
            "final_report.md",
            report.final_report_markdown,
        )
        if report.audit_seal:
            _write_text_file(
                archive,
                included_files,
                "audit_seal.json",
                json.dumps(report.audit_seal.model_dump(mode="json"), indent=2),
            )
        if report.telemetry_card:
            _write_text_file(
                archive,
                included_files,
                "telemetry_card.md",
                report.telemetry_card.markdown,
            )
        if benchmark_summary:
            _write_text_file(
                archive,
                included_files,
                "amd_benchmark_results.json",
                json.dumps(benchmark_summary.model_dump(mode="json"), indent=2),
            )

        _write_text_file(
            archive,
            included_files,
            "model_router.csv",
            _build_model_router_csv(report),
        )
        _write_text_file(
            archive,
            included_files,
            "strategy_comparison.csv",
            _build_strategy_csv(report),
        )

        for packet in report.escalation_packets:
            base_name = packet.incident_id.lower()
            _write_text_file(
                archive,
                included_files,
                f"escalation_packets/{base_name}.md",
                packet.markdown_body,
            )
            _write_text_file(
                archive,
                included_files,
                f"escalation_packets/{base_name}.eml",
                packet.eml_content,
            )

        _write_text_file(
            archive,
            included_files,
            "run_summary.json",
            json.dumps(_build_run_summary(report, benchmark_summary), indent=2),
        )

    return WarRoomPacketArtifact(
        file_name=file_name,
        content=buffer.getvalue(),
        included_files=included_files,
        description="Download a complete operational handoff bundle for this run.",
    )


def _build_model_router_csv(report: AgentRunResult) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=[
            "incident_id",
            "title",
            "risk_tier",
            "execution_mode",
            "recommended_model",
            "expected_latency_ms",
            "expected_cost_usd",
            "owner_name",
            "owner_email",
            "reason",
            "policy_hits",
        ],
    )
    writer.writeheader()
    for route in report.model_routes:
        writer.writerow(
            {
                "incident_id": route.incident_id,
                "title": route.title,
                "risk_tier": route.risk_tier,
                "execution_mode": route.selected_execution_mode,
                "recommended_model": route.recommended_model,
                "expected_latency_ms": route.expected_latency_ms,
                "expected_cost_usd": route.expected_cost_usd,
                "owner_name": route.owner_name,
                "owner_email": route.owner_email,
                "reason": route.reason,
                "policy_hits": ", ".join(route.policy_hits),
            }
        )
    return output.getvalue()


def _build_strategy_csv(report: AgentRunResult) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=[
            "strategy_name",
            "description",
            "total_estimated_latency_ms",
            "p95_latency_risk",
            "estimated_cost_usd",
            "expected_quality_score",
            "risk_coverage_score",
            "human_review_count",
            "model_calls",
            "deterministic_steps",
            "recommended",
        ],
    )
    writer.writeheader()
    for strategy in report.strategy_results:
        writer.writerow(strategy.model_dump(mode="json", include=set(writer.fieldnames)))
    return output.getvalue()


def _build_run_summary(
    report: AgentRunResult,
    benchmark_summary: Optional[AmdBenchmarkSummary],
) -> dict[str, object]:
    return {
        "run_id": report.run_id,
        "recommended_strategy": report.recommended_strategy.strategy_name
        if report.recommended_strategy
        else None,
        "sla_status": report.sla_monitor_result.status if report.sla_monitor_result else None,
        "benchmark_run_id": benchmark_summary.run_id if benchmark_summary else None,
        "benchmark_model": benchmark_summary.model if benchmark_summary else None,
        "human_review_count": len(report.escalation_packets),
        "policy_compliance_status": report.policy_compliance.compliance_status
        if report.policy_compliance
        else None,
        "historical_analytics": report.historical_analytics.model_dump(mode="json")
        if report.historical_analytics
        else None,
        "llm_runtime_info": report.llm_runtime_info,
    }


def _write_text_file(
    archive: zipfile.ZipFile,
    included_files: list[str],
    path: str,
    content: str,
) -> None:
    archive.writestr(path, content)
    included_files.append(path)
