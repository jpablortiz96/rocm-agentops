"""Reporter Agent: assembles the final report."""

from typing import List

from core.llm_client import LLMClient, llm
from core.report_builder import ReportBuilder
from core.schemas import AgentTrace, FinalReport, Incident, OptimizationRecommendation, ROCmReadinessReport, TriageResult
from core.scoring import compute_overall_trust
from core.tracing import TraceBuilder


class ReporterAgent:
    """Builds the final downloadable report."""

    SYSTEM_PROMPT = (
        "You are a technical product analyst writing an audit report for hackathon judges. "
        "Be clear, honest, concise, and do not overclaim production deployment."
    )

    def __init__(self, llm_client: LLMClient = llm):
        self.llm = llm_client
        self.name = "reporter"
        self.last_llm_meta = None

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

    def generate_executive_summary(
        self,
        incident_count: int,
        triage_count: int,
        optimization_count: int,
        trace_event_count: int,
    ) -> str:
        """Generate a brief executive summary narrative."""
        fallback = (
            f"ROCm AgentOps processed {incident_count} incidents through deterministic scoring "
            f"and generated {optimization_count} optimization recommendations. "
            f"Trace contains {trace_event_count} events. All scores are mathematically derived."
        )
        user_prompt = (
            f"Write a 2-sentence executive summary for an incident triage report. "
            f"Cover {incident_count} incidents, {triage_count} triage decisions, "
            f"{optimization_count} optimizations, and {trace_event_count} trace events. "
            "Be concise and honest."
        )
        result = self.llm.chat(self.SYSTEM_PROMPT, user_prompt, fallback=fallback)
        self.last_llm_meta = result
        return result["content"]
