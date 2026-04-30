"""Build downloadable reports from triage results."""

import json
from datetime import datetime
from typing import List

from core.schemas import AgentTrace, FinalReport, Incident, OptimizationRecommendation, ROCmReadinessReport, TriageResult


class ReportBuilder:
    """Assemble markdown, JSON, and summary reports."""

    def __init__(self):
        self.parts: List[str] = []

    def add_header(self, title: str, version: str = "0.1.0") -> "ReportBuilder":
        self.parts.append(f"# {title}\n")
        self.parts.append(f"**Generated:** {datetime.utcnow().isoformat()}Z  \n")
        self.parts.append(f"**Version:** {version}\n")
        return self

    def add_incidents(self, incidents: List[Incident]) -> "ReportBuilder":
        self.parts.append("## Incidents\n")
        for inc in incidents:
            self.parts.append(
                f"- **{inc.id}** | `{inc.severity_hint.value}` | {inc.title} ({inc.system})\n"
            )
        self.parts.append("\n")
        return self

    def add_triage(self, results: List[TriageResult]) -> "ReportBuilder":
        self.parts.append("## Triage Results\n")
        for r in results:
            self.parts.append(f"### {r.incident_id} — Rank {r.priority_rank}\n")
            self.parts.append(f"- **Confidence:** {r.confidence_score}\n")
            self.parts.append(f"- **Cost Estimate:** ${r.estimated_cost_usd}\n")
            self.parts.append(f"- **Latency Estimate:** {r.estimated_latency_ms} ms\n")
            self.parts.append(f"- **Reasoning:** {r.reasoning}\n")
            if r.risk_flags:
                self.parts.append(f"- **Risk Flags:** {', '.join(r.risk_flags)}\n")
            if r.recommendations:
                self.parts.append(f"- **Recommendations:** {', '.join(r.recommendations)}\n")
            self.parts.append("\n")
        return self

    def add_trace_summary(self, trace: AgentTrace) -> "ReportBuilder":
        self.parts.append("## Agent Trace\n")
        self.parts.append(f"**Trace ID:** {trace.trace_id}  \n")
        self.parts.append(f"**Workflow:** {trace.workflow_name}  \n")
        total_latency = sum(s.latency_ms for s in trace.steps)
        self.parts.append(f"**Total Latency:** {total_latency} ms  \n")
        self.parts.append("\n| Step | Agent | Status | Latency (ms) |\n")
        self.parts.append("|------|-------|--------|-------------|\n")
        for step in trace.steps:
            self.parts.append(
                f"| {step.step_name} | {step.agent_name} | {step.status} | {step.latency_ms} |\n"
            )
        self.parts.append("\n")
        return self

    def add_optimizations(self, opts: List[OptimizationRecommendation]) -> "ReportBuilder":
        self.parts.append("## Optimization Recommendations\n")
        for o in opts:
            self.parts.append(f"### {o.title} ({o.category}, {o.estimated_impact} impact)\n")
            self.parts.append(f"{o.description}\n")
            if o.action_items:
                self.parts.append("- **Actions:**\n")
                for a in o.action_items:
                    self.parts.append(f"  - {a}\n")
            self.parts.append("\n")
        return self

    def add_rocm(self, report: ROCmReadinessReport) -> "ReportBuilder":
        self.parts.append("## ROCm / AMD Readiness\n")
        self.parts.append(f"- **Model Compatible:** {'Yes' if report.model_compatible else 'No'}\n")
        self.parts.append(f"- **GPU Recommendation:** {report.gpu_recommendation}\n")
        if report.kernel_optimizations:
            self.parts.append(f"- **Kernels:** {', '.join(report.kernel_optimizations)}\n")
        if report.quantization_suggestion:
            self.parts.append(f"- **Quantization:** {report.quantization_suggestion}\n")
        if report.notes:
            self.parts.append(f"- **Notes:** {', '.join(report.notes)}\n")
        self.parts.append("\n")
        return self

    def build_markdown(self) -> str:
        return "\n".join(self.parts)

    def build_json_report(self, report: FinalReport) -> str:
        return report.model_dump_json(indent=2)

    @staticmethod
    def from_final_report(report: FinalReport) -> str:
        """Convenience: build markdown from a FinalReport schema."""
        builder = (
            ReportBuilder()
            .add_header("ROCm AgentOps Report", version="0.1.0")
            .add_incidents(report.incidents)
            .add_triage(report.triage_results)
        )
        if report.trace:
            builder.add_trace_summary(report.trace)
        if report.optimizations:
            builder.add_optimizations(report.optimizations)
        if report.rocm_report:
            builder.add_rocm(report.rocm_report)
        builder.parts.append(f"\n## Overall Trust Score\n**{report.overall_trust_score}**\n")
        return builder.build_markdown()
