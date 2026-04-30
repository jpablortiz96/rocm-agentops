"""Reporter Agent: assembles the final report."""

from typing import List

from core.report_builder import ReportBuilder
from core.schemas import AgentTrace, FinalReport, Incident, OptimizationRecommendation, ROCmReadinessReport, TriageResult
from core.scoring import compute_overall_trust
from core.tracing import TraceBuilder


class ReporterAgent:
    """Builds the final downloadable report."""

    def __init__(self):
        self.name = "reporter"

    def build_report(
        self,
        incidents: List[Incident],
        triage_results: List[TriageResult],
        trace: AgentTrace,
        optimizations: List[OptimizationRecommendation],
        rocm_report: ROCmReadinessReport,
        trace_builder: TraceBuilder,
    ) -> FinalReport:
        """Assemble everything into a FinalReport."""
        trace_builder.start_step(
            "build_report", self.name, input_summary=f"{len(triage_results)} results"
        )

        trust = compute_overall_trust(triage_results)
        report = FinalReport(
            report_id=f"report-{trace.trace_id}",
            incidents=incidents,
            triage_results=triage_results,
            trace=trace,
            optimizations=optimizations,
            rocm_report=rocm_report,
            overall_trust_score=trust,
        )
        report.summary_md = ReportBuilder.from_final_report(report)

        trace_builder.end_step(
            output_summary=f"Report ready. Trust={trust}",
            status="success",
        )
        return report
