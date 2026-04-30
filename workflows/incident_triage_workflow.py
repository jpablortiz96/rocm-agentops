"""Incident Triage Workflow: orchestrates deterministic scoring end-to-end."""

from typing import List

from core.llm_client import LLMClient, llm
from core.schemas import (
    AgentRunResult,
    AgentTraceEvent,
    Incident,
    OptimizationRecommendation,
    RiskFlag,
    ROCmReadinessReport,
    TriageDecision,
)
from core.scoring import calculate_incident_priority_score
from core.tracing import create_run_id, elapsed_ms, make_trace_event, start_timer, utc_now_iso


class IncidentTriageWorkflow:
    """End-to-end deterministic workflow for incident triage."""

    def __init__(self, llm_client: LLMClient = llm):
        self.llm = llm_client
        self.name = "incident_triage"

    def run(self, incidents: List[Incident]) -> AgentRunResult:
        """Execute the deterministic workflow and return an AgentRunResult."""
        run_id = create_run_id()
        trace: List[AgentTraceEvent] = []

        # ------------------------------------------------------------------
        # 1. Workflow started
        # ------------------------------------------------------------------
        t0 = start_timer()
        trace.append(
            make_trace_event(
                run_id=run_id,
                agent_name="orchestrator",
                step_name="workflow_started",
                input_summary=f"Processing {len(incidents)} incidents",
                output_summary="Workflow initialized",
                latency_ms=elapsed_ms(t0),
                status="success",
                estimated_tokens=0,
                estimated_cost_usd=0.0,
            )
        )

        # ------------------------------------------------------------------
        # 2. Deterministic scoring
        # ------------------------------------------------------------------
        t1 = start_timer()
        triage_results: List[TriageDecision] = []
        for inc in incidents:
            score = calculate_incident_priority_score(inc)
            decision = TriageDecision(
                incident_id=inc.id,
                title=inc.title,
                system=inc.system,
                status=inc.status.value,
                severity_hint=inc.severity_hint.value,
                priority_score=score["priority_score"],
                confidence_score=score["confidence_score"],
                trust_score=score["trust_score"],
                recommended_action=score["recommended_action"],
                reasons=score["reasons"],
                risk_flags=score["risk_flags"],
                human_review_required=score["human_review_required"],
            )
            triage_results.append(decision)

        # Sort by priority_score descending
        triage_results.sort(key=lambda d: d.priority_score, reverse=True)

        trace.append(
            make_trace_event(
                run_id=run_id,
                agent_name="scoring_engine",
                step_name="deterministic_scoring_completed",
                input_summary=f"Scored {len(incidents)} incidents",
                output_summary=f"Top priority: {triage_results[0].incident_id if triage_results else 'none'}",
                latency_ms=elapsed_ms(t1),
                status="success",
                estimated_tokens=0,
                estimated_cost_usd=0.0,
            )
        )

        # ------------------------------------------------------------------
        # 3. Optimization recommendations
        # ------------------------------------------------------------------
        t2 = start_timer()
        optimizations = self._build_optimizations(incidents, triage_results)
        trace.append(
            make_trace_event(
                run_id=run_id,
                agent_name="optimizer",
                step_name="optimization_recommendations",
                input_summary=f"Analyzed {len(triage_results)} triage decisions",
                output_summary=f"Generated {len(optimizations)} recommendations",
                latency_ms=elapsed_ms(t2),
                status="success",
                estimated_tokens=800,
                estimated_cost_usd=0.0032,
            )
        )

        # ------------------------------------------------------------------
        # 4. ROCm readiness report
        # ------------------------------------------------------------------
        t3 = start_timer()
        rocm_report = self._build_rocm_report(incidents, triage_results)
        trace.append(
            make_trace_event(
                run_id=run_id,
                agent_name="rocm_advisor",
                step_name="rocm_readiness_check",
                input_summary="Evaluated ROCm relevance",
                output_summary="Report ready" if rocm_report else "No ROCm incidents",
                latency_ms=elapsed_ms(t3),
                status="success",
                estimated_tokens=600,
                estimated_cost_usd=0.0024,
            )
        )

        # ------------------------------------------------------------------
        # 5. Final markdown report
        # ------------------------------------------------------------------
        t4 = start_timer()
        final_markdown = self._build_markdown_report(run_id, incidents, triage_results, optimizations, rocm_report, trace)
        trace.append(
            make_trace_event(
                run_id=run_id,
                agent_name="reporter",
                step_name="final_report_assembled",
                input_summary="Assembling report",
                output_summary=f"Report length: {len(final_markdown)} chars",
                latency_ms=elapsed_ms(t4),
                status="success",
                estimated_tokens=1200,
                estimated_cost_usd=0.0048,
            )
        )

        return AgentRunResult(
            run_id=run_id,
            triage_results=triage_results,
            trace=trace,
            optimizations=optimizations,
            rocm_report=rocm_report,
            final_report_markdown=final_markdown,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_optimizations(
        self, incidents: List[Incident], triage_results: List[TriageDecision]
    ) -> List[OptimizationRecommendation]:
        opts: List[OptimizationRecommendation] = []

        high_priority = [t for t in triage_results if t.priority_score >= 60]
        inference_incidents = [i for i in incidents if i.system == "inference"]
        security_incidents = [i for i in incidents if i.system == "security"]
        missing_evidence = [i for i in incidents if len(i.evidence) == 0]

        if inference_incidents:
            opts.append(
                OptimizationRecommendation(
                    category="latency",
                    title="ROCm Batching and Kernel Fusion",
                    description="Inference incidents indicate GPU stack sensitivity. Enable vLLM continuous batching and hipBLASLt fusion.",
                    recommendation="Enable vLLM continuous batching on MI300X with hipBLASLt fused kernels. Profile with rocProf.",
                    expected_benefit="20-40% throughput improvement on AMD GPUs",
                    complexity="medium",
                    estimated_impact="high",
                    action_items=[
                        "Enable vLLM --enable-chunked-prefill",
                        "Switch to hipBLASLt for GEMM fusion",
                        "Profile with rocProf and optimize Triton kernels",
                    ],
                )
            )

        if high_priority:
            opts.append(
                OptimizationRecommendation(
                    category="trust",
                    title="Faster Triage for High-Priority Incidents",
                    description="Multiple high-priority incidents suggest need for deterministic pre-filtering before LLM calls.",
                    recommendation="Use deterministic scoring as a routing layer to skip LLM calls for obvious P0/P1 incidents.",
                    expected_benefit="Reduce triage latency by 60% for critical incidents",
                    complexity="low",
                    estimated_impact="high",
                    action_items=[
                        "Route priority_score >= 80 directly to on-call",
                        "Batch priority_score < 40 for async LLM review",
                    ],
                )
            )

        if security_incidents:
            opts.append(
                OptimizationRecommendation(
                    category="trust",
                    title="Security Evidence Pipeline",
                    description="Security incidents lack structured evidence. Enrich with cloud trail and SIEM links.",
                    recommendation="Auto-attach CloudTrail, GuardDuty, and SIEM links to security incidents.",
                    expected_benefit="Faster forensic turnaround",
                    complexity="medium",
                    estimated_impact="medium",
                    action_items=[
                        "Integrate CloudTrail lookup",
                        "Attach GuardDuty finding IDs",
                    ],
                )
            )

        if missing_evidence:
            opts.append(
                OptimizationRecommendation(
                    category="accuracy",
                    title="Evidence Collection Automation",
                    description=f"{len(missing_evidence)} incidents arrived without evidence.",
                    recommendation="Auto-collect logs, metrics, and traces when an incident is opened.",
                    expected_benefit="Higher confidence scores and fewer false positives",
                    complexity="medium",
                    estimated_impact="medium",
                    action_items=[
                        "Runbook-driven evidence collector",
                        "Link Grafana dashboards automatically",
                    ],
                )
            )

        if not opts:
            opts.append(
                OptimizationRecommendation(
                    category="cost",
                    title="Operational Health",
                    description="No critical optimizations detected. Monitor baseline.",
                    recommendation="Continue monitoring and maintain SLOs.",
                    expected_benefit="Stability",
                    complexity="low",
                    estimated_impact="low",
                )
            )

        return opts

    def _build_rocm_report(
        self, incidents: List[Incident], triage_results: List[TriageDecision]
    ) -> ROCmReadinessReport:
        inference_incidents = [i for i in incidents if i.system == "inference"]
        if not inference_incidents:
            return ROCmReadinessReport(
                summary="No inference incidents detected. ROCm readiness is not a current blocker.",
                gpu_relevant_steps=[],
                rocm_optimizations=[],
                batching_opportunities=[],
                estimated_impact="low",
                limitations=[],
            )

        rocm_keywords = ["mi300x", "rocm", "triton", "gpu", "thermal", "throughput"]
        relevant = [
            i for i in inference_incidents
            if any(k in f"{i.title} {i.description}".lower() for k in rocm_keywords)
        ]

        summary = (
            f"{len(relevant)} inference incident(s) relate to AMD/ROCm stack. "
            "Recommend immediate GPU profiling and kernel optimization."
        )

        return ROCmReadinessReport(
            summary=summary,
            gpu_relevant_steps=[i.id for i in relevant],
            rocm_optimizations=[
                "Enable hipBLASLt for fused GEMM operations",
                "Use MIOpen for optimized convolutions",
                "Switch to RCCL for multi-GPU communication",
                "Quantize to FP8/INT8 via AMD-quant for higher throughput",
            ],
            batching_opportunities=[
                "vLLM continuous batching on MI300X",
                "Dynamic split-fuse for decode-heavy workloads",
            ],
            estimated_impact="high",
            limitations=[
                "ROCm 6.1+ required for best Flash Attention support",
                "Some Triton kernels may need manual tuning on MI300X",
                "Docker base image must use rocm/pytorch:latest",
            ],
            model_compatible=True,
            gpu_recommendation="MI300X",
            kernel_optimizations=["hipBLASLt", "MIOpen", "RCCL"],
            quantization_suggestion="FP8 / INT8 via AMD-quant",
            notes=[
                "ROCm 6.1+ recommended for best Flash Attention support",
                "Ensure docker image uses rocm/pytorch base",
            ],
        )

    def _build_markdown_report(
        self,
        run_id: str,
        incidents: List[Incident],
        triage_results: List[TriageDecision],
        optimizations: List[OptimizationRecommendation],
        rocm_report: ROCmReadinessReport,
        trace: List[AgentTraceEvent],
    ) -> str:
        lines: List[str] = []
        lines.append(f"# ROCm AgentOps Report — {run_id}")
        lines.append(f"**Generated:** {utc_now_iso()}  ")
        lines.append(f"**Incidents Processed:** {len(incidents)}  ")
        lines.append("")

        lines.append("## Triage Results (Ranked)")
        for rank, d in enumerate(triage_results, start=1):
            lines.append(f"### {rank}. {d.incident_id} — {d.title}")
            lines.append(f"- **System:** {d.system} | **Status:** {d.status} | **Severity:** {d.severity_hint}")
            lines.append(f"- **Priority Score:** {d.priority_score}")
            lines.append(f"- **Confidence:** {d.confidence_score}")
            lines.append(f"- **Trust:** {d.trust_score}")
            lines.append(f"- **Action:** {d.recommended_action}")
            lines.append(f"- **Human Review:** {'Yes' if d.human_review_required else 'No'}")
            if d.reasons:
                lines.append("- **Reasons:**")
                for r in d.reasons:
                    lines.append(f"  - {r}")
            if d.risk_flags:
                lines.append("- **Risk Flags:**")
                for f in d.risk_flags:
                    lines.append(f"  - **{f.label}** ({f.severity}): {f.explanation}")
            lines.append("")

        lines.append("## Optimization Recommendations")
        for o in optimizations:
            lines.append(f"### {o.title}")
            lines.append(f"- **Category:** {o.category} | **Impact:** {o.estimated_impact} | **Complexity:** {o.complexity}")
            if o.description:
                lines.append(f"- **Description:** {o.description}")
            if o.recommendation:
                lines.append(f"- **Recommendation:** {o.recommendation}")
            if o.expected_benefit:
                lines.append(f"- **Expected Benefit:** {o.expected_benefit}")
            if o.action_items:
                lines.append("- **Actions:**")
                for a in o.action_items:
                    lines.append(f"  - {a}")
            lines.append("")

        lines.append("## ROCm / AMD Readiness")
        if rocm_report:
            lines.append(f"**Summary:** {rocm_report.summary}")
            lines.append(f"**Estimated Impact:** {rocm_report.estimated_impact}")
            if rocm_report.gpu_relevant_steps:
                lines.append(f"**GPU Relevant Steps:** {', '.join(rocm_report.gpu_relevant_steps)}")
            if rocm_report.rocm_optimizations:
                lines.append("**ROCm Optimizations:**")
                for opt in rocm_report.rocm_optimizations:
                    lines.append(f"- {opt}")
            if rocm_report.batching_opportunities:
                lines.append("**Batching Opportunities:**")
                for b in rocm_report.batching_opportunities:
                    lines.append(f"- {b}")
            if rocm_report.limitations:
                lines.append("**Limitations:**")
                for lim in rocm_report.limitations:
                    lines.append(f"- {lim}")
        else:
            lines.append("No ROCm readiness report generated.")
        lines.append("")

        lines.append("## Trace Summary")
        lines.append(f"Workflow executed with run ID `{run_id}`.")
        lines.append("")
        lines.append("| Step | Agent | Latency (ms) | Est. Tokens | Est. Cost |")
        lines.append("|------|-------|-------------|------------|----------|")
        for evt in trace:
            lines.append(
                f"| {evt.step_name} | {evt.agent_name} | {evt.latency_ms} | {evt.estimated_tokens} | ${evt.estimated_cost_usd:.4f} |"
            )
        lines.append("")
        lines.append("> **Note:** All costs shown are simulated estimates for demonstration purposes. "
                    "Deterministic scoring steps incur no LLM cost. Only optimizer, ROCm advisor, and reporter steps include mock LLM-like costs."
        )
        lines.append("")

        return "\n".join(lines)
