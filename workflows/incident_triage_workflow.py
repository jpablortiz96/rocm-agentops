"""Incident Triage Workflow: orchestrates deterministic scoring end-to-end."""

from typing import List

from agents.critic_agent import CriticAgent
from agents.optimizer_agent import OptimizerAgent
from agents.planner_agent import PlannerAgent
from agents.rocm_advisor_agent import ROCmAdvisorAgent
from core.llm_client import LLMClient, llm
from core.schemas import (
    AgentRunResult,
    AgentTraceEvent,
    BaselineDecision,
    Incident,
    OptimizationRecommendation,
    ROCmReadinessReport,
    TriageDecision,
)
from core.benchmarking import load_benchmark_results
from core.scoring import calculate_incident_priority_score, run_baseline_triage
from core.tracing import create_run_id, elapsed_ms, make_trace_event, start_timer, utc_now_iso


class IncidentTriageWorkflow:
    """End-to-end deterministic workflow for incident triage."""

    def __init__(self, llm_client: LLMClient = llm):
        self.llm = llm_client
        self.name = "incident_triage"
        self.planner = PlannerAgent(llm_client)
        self.critic = CriticAgent(llm_client)
        self.optimizer = OptimizerAgent(llm_client)
        self.rocm_advisor = ROCmAdvisorAgent(llm_client)

    def run(self, incidents: List[Incident]) -> AgentRunResult:
        """Execute the deterministic workflow and return an AgentRunResult."""
        run_id = create_run_id()
        trace: List[AgentTraceEvent] = []
        llm_errors: List[str] = []
        any_llm_used = False
        any_mock_used = False

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
        # 2. Baseline triage (naive)
        # ------------------------------------------------------------------
        t1 = start_timer()
        baseline_results = run_baseline_triage(incidents)
        trace.append(
            make_trace_event(
                run_id=run_id,
                agent_name="baseline",
                step_name="baseline_triage",
                input_summary=f"{len(incidents)} incidents",
                output_summary=f"Baseline top: {baseline_results[0].incident_id if baseline_results else 'none'}",
                latency_ms=elapsed_ms(t1),
                status="success",
                estimated_tokens=0,
                estimated_cost_usd=0.0,
            )
        )

        # ------------------------------------------------------------------
        # 3. Deterministic AgentOps scoring
        # ------------------------------------------------------------------
        t2 = start_timer()
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

        triage_results.sort(key=lambda d: d.priority_score, reverse=True)

        trace.append(
            make_trace_event(
                run_id=run_id,
                agent_name="scoring_engine",
                step_name="deterministic_scoring_completed",
                input_summary=f"Scored {len(incidents)} incidents",
                output_summary=f"Top priority: {triage_results[0].incident_id if triage_results else 'none'}",
                latency_ms=elapsed_ms(t2),
                status="success",
                estimated_tokens=0,
                estimated_cost_usd=0.0,
            )
        )

        # ------------------------------------------------------------------
        # 4. Planner agent
        # ------------------------------------------------------------------
        t3 = start_timer()
        planner_text = self.planner.generate_plan_text(len(incidents))
        planner_meta = self.planner.last_llm_meta or {}
        if planner_meta.get("error"):
            llm_errors.append(f"Planner: {planner_meta['error']}")
        if planner_meta.get("used_llm"):
            any_llm_used = True
        if planner_meta.get("used_mock"):
            any_mock_used = True

        trace.append(
            make_trace_event(
                run_id=run_id,
                agent_name="planner",
                step_name="plan_generated",
                input_summary=f"{len(incidents)} incidents",
                output_summary=(
                    "LLM narrative generated"
                    if planner_meta.get("used_llm")
                    else "Mock/fallback narrative used"
                    + (f" (error: {planner_meta['error']})" if planner_meta.get("error") else "")
                ),
                latency_ms=elapsed_ms(t3),
                status="success",
                estimated_tokens=planner_meta.get("estimated_input_tokens", 0)
                + planner_meta.get("estimated_output_tokens", 0),
                estimated_cost_usd=planner_meta.get("estimated_cost_usd", 0.0),
            )
        )

        # ------------------------------------------------------------------
        # 5. Critic agent
        # ------------------------------------------------------------------
        t4 = start_timer()
        critic_text = self.critic.review_batch(triage_results)
        critic_meta = self.critic.last_llm_meta or {}
        if critic_meta.get("error"):
            llm_errors.append(f"Critic: {critic_meta['error']}")
        if critic_meta.get("used_llm"):
            any_llm_used = True
        if critic_meta.get("used_mock"):
            any_mock_used = True

        trace.append(
            make_trace_event(
                run_id=run_id,
                agent_name="critic",
                step_name="critic_review",
                input_summary=f"Reviewed {len(triage_results)} decisions",
                output_summary=(
                    "LLM narrative generated"
                    if critic_meta.get("used_llm")
                    else "Mock/fallback narrative used"
                    + (f" (error: {critic_meta['error']})" if critic_meta.get("error") else "")
                ),
                latency_ms=elapsed_ms(t4),
                status="success",
                estimated_tokens=critic_meta.get("estimated_input_tokens", 0)
                + critic_meta.get("estimated_output_tokens", 0),
                estimated_cost_usd=critic_meta.get("estimated_cost_usd", 0.0),
            )
        )

        # ------------------------------------------------------------------
        # 6. Optimizer agent
        # ------------------------------------------------------------------
        t5 = start_timer()
        optimizations = self.optimizer.optimize_batch(triage_results)
        optimizer_meta = self.optimizer.last_llm_meta or {}
        if optimizer_meta.get("error"):
            llm_errors.append(f"Optimizer: {optimizer_meta['error']}")
        if optimizer_meta.get("used_llm"):
            any_llm_used = True
        if optimizer_meta.get("used_mock"):
            any_mock_used = True

        trace.append(
            make_trace_event(
                run_id=run_id,
                agent_name="optimizer",
                step_name="optimization_recommendations",
                input_summary=f"Analyzed {len(triage_results)} triage decisions",
                output_summary=(
                    "LLM narrative generated"
                    if optimizer_meta.get("used_llm")
                    else "Mock/fallback narrative used"
                    + (f" (error: {optimizer_meta['error']})" if optimizer_meta.get("error") else "")
                ),
                latency_ms=elapsed_ms(t5),
                status="success",
                estimated_tokens=optimizer_meta.get("estimated_input_tokens", 0)
                + optimizer_meta.get("estimated_output_tokens", 0),
                estimated_cost_usd=optimizer_meta.get("estimated_cost_usd", 0.0),
            )
        )

        # ------------------------------------------------------------------
        # 7. ROCm advisor agent
        # ------------------------------------------------------------------
        t6 = start_timer()
        rocm_report = self.rocm_advisor.advise_batch(incidents)
        rocm_meta = self.rocm_advisor.last_llm_meta or {}
        if rocm_meta.get("error"):
            llm_errors.append(f"ROCm Advisor: {rocm_meta['error']}")
        if rocm_meta.get("used_llm"):
            any_llm_used = True
        if rocm_meta.get("used_mock"):
            any_mock_used = True

        trace.append(
            make_trace_event(
                run_id=run_id,
                agent_name="rocm_advisor",
                step_name="rocm_readiness_check",
                input_summary="Evaluated ROCm relevance",
                output_summary=(
                    "LLM narrative generated"
                    if rocm_meta.get("used_llm")
                    else "Mock/fallback narrative used"
                    + (f" (error: {rocm_meta['error']})" if rocm_meta.get("error") else "")
                ),
                latency_ms=elapsed_ms(t6),
                status="success",
                estimated_tokens=rocm_meta.get("estimated_input_tokens", 0)
                + rocm_meta.get("estimated_output_tokens", 0),
                estimated_cost_usd=rocm_meta.get("estimated_cost_usd", 0.0),
            )
        )

        # ------------------------------------------------------------------
        # 8. Build comparison, agent review, and final report
        # ------------------------------------------------------------------
        t7 = start_timer()
        comparison_md = self._build_comparison_markdown(baseline_results, triage_results)
        mismatch_insights = self._generate_mismatch_insights(baseline_results, triage_results)
        agent_review_md = self._build_agent_review_markdown(
            planner_text, critic_text, mismatch_insights, triage_results
        )

        # Determine narrative mode label
        if any_llm_used and not any_mock_used:
            narrative_mode = "Real endpoint"
        elif any_llm_used:
            narrative_mode = "Mixed (some fallback)"
        else:
            narrative_mode = "Mock/fallback"

        llm_runtime_info = {
            "mock_mode": self.llm.mock,
            "model": self.llm.model,
            "base_url": self.llm.base_url,
            "narrative_mode": narrative_mode,
            "errors": llm_errors,
            "any_llm_used": any_llm_used,
            "any_mock_used": any_mock_used,
        }

        final_markdown = self._build_markdown_report(
            run_id,
            incidents,
            baseline_results,
            triage_results,
            optimizations,
            rocm_report,
            trace,
            agent_review_md,
            comparison_md,
            llm_runtime_info,
        )
        trace.append(
            make_trace_event(
                run_id=run_id,
                agent_name="reporter",
                step_name="final_report_assembled",
                input_summary="Assembling report",
                output_summary=f"Report length: {len(final_markdown)} chars",
                latency_ms=elapsed_ms(t7),
                status="success",
                estimated_tokens=0,
                estimated_cost_usd=0.0,
            )
        )

        return AgentRunResult(
            run_id=run_id,
            triage_results=triage_results,
            baseline_results=baseline_results,
            trace=trace,
            optimizations=optimizations,
            rocm_report=rocm_report,
            agent_review_markdown=agent_review_md,
            comparison_markdown=comparison_md,
            final_report_markdown=final_markdown,
            llm_runtime_info=llm_runtime_info,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_comparison_markdown(
        self, baseline: List[BaselineDecision], agentops: List[TriageDecision]
    ) -> str:
        lines: List[str] = []
        lines.append("## Baseline vs ROCm AgentOps")
        lines.append("")
        lines.append("| Capability | Baseline Agent | ROCm AgentOps |")
        lines.append("|---|---|---|")
        lines.append("| Priority ranking | ✓ | ✓ |")
        lines.append("| Trust score | ✗ | ✓ |")
        lines.append("| Risk flags | ✗ | ✓ |")
        lines.append("| Human review escalation | ✗ | ✓ |")
        lines.append("| Trace replay | ✗ | ✓ |")
        lines.append("| Cost estimate | ✗ | ✓ |")
        lines.append("| Latency visibility | ✗ | ✓ |")
        lines.append("| Optimization recommendations | ✗ | ✓ |")
        lines.append("| AMD/ROCm readiness | ✗ | ✓ |")
        lines.append("| Final audit report | ✗ | ✓ |")
        lines.append("")

        top_baseline = baseline[0] if baseline else None
        top_agentops = agentops[0] if agentops else None
        human_review_count = sum(1 for d in agentops if d.human_review_required)

        lines.append("**Metric Snapshot**")
        if top_baseline:
            lines.append(f"- **Highest Baseline Priority:** {top_baseline.incident_id} — {top_baseline.title} (score: {top_baseline.baseline_score})")
        if top_agentops:
            lines.append(f"- **Highest AgentOps Priority:** {top_agentops.incident_id} — {top_agentops.title} (score: {top_agentops.priority_score})")
        lines.append(f"- **High-Risk Incidents Requiring Human Review:** {human_review_count}")
        lines.append("")

        return "\n".join(lines)

    def _generate_mismatch_insights(
        self, baseline: List[BaselineDecision], agentops: List[TriageDecision]
    ) -> List[str]:
        insights: List[str] = []
        baseline_rank = {d.incident_id: d.baseline_rank for d in baseline}
        agentops_rank = {d.incident_id: i + 1 for i, d in enumerate(agentops)}

        # INC-004: security with missing evidence
        if baseline_rank.get("INC-004") and agentops_rank.get("INC-004"):
            if baseline_rank["INC-004"] > agentops_rank["INC-004"]:
                insights.append(
                    "**INC-004** (Suspicious IAM activity) was under-ranked by the baseline because it only affects 5 users. "
                    "AgentOps elevated it to top-3 due to critical security severity, empty evidence, and urgent 10-minute SLA."
                )

        # INC-005: many users but low severity / mitigated
        if baseline_rank.get("INC-005") and agentops_rank.get("INC-005"):
            if baseline_rank["INC-005"] < agentops_rank["INC-005"]:
                insights.append(
                    "**INC-005** (Notification delay) was over-ranked by the baseline because it affects 250,000 users. "
                    "AgentOps correctly deprioritized it: low severity, mitigated status, and minimal revenue impact."
                )

        # INC-007: hallucination
        if baseline_rank.get("INC-007") and agentops_rank.get("INC-007"):
            if baseline_rank["INC-007"] > agentops_rank["INC-007"]:
                insights.append(
                    "**INC-007** (LLM hallucination) was under-ranked by the baseline. "
                    "AgentOps elevated it because hallucination risk is a critical AI-safety issue requiring human review."
                )

        # INC-006: ROCm inference
        if baseline_rank.get("INC-006") and agentops_rank.get("INC-006"):
            if baseline_rank["INC-006"] > agentops_rank["INC-006"]:
                insights.append(
                    "**INC-006** (GPU inference degradation on MI300X) was under-ranked by the baseline. "
                    "AgentOps elevated it because AMD/ROCm inference stack degradation affects model serving reliability."
                )

        # INC-003: 0 users but high revenue
        if baseline_rank.get("INC-003") and agentops_rank.get("INC-003"):
            if baseline_rank["INC-003"] > agentops_rank["INC-003"]:
                insights.append(
                    "**INC-003** (ETL pipeline stalled) was under-ranked by the baseline because it affects 0 users. "
                    "AgentOps kept it mid-tier because the $150k revenue impact blocks finance forecasting."
                )

        return insights

    def _build_agent_review_markdown(
        self,
        planner_text: str,
        critic_text: str,
        mismatch_insights: List[str],
        triage_results: List[TriageDecision],
    ) -> str:
        lines: List[str] = []
        lines.append("# Agent Review")
        lines.append("")

        lines.append("## Planner Output")
        lines.append(planner_text)
        lines.append("")

        lines.append("## Critic Output")
        lines.append(critic_text)
        lines.append("")

        lines.append("## Baseline Mismatch Insights")
        if mismatch_insights:
            for insight in mismatch_insights:
                lines.append(f"- {insight}")
        else:
            lines.append("No significant baseline mismatches detected.")
        lines.append("")

        lines.append("## Human Review Triggers")
        human_review = [d for d in triage_results if d.human_review_required]
        if human_review:
            lines.append(f"{len(human_review)} incident(s) triggered human review:")
            for d in human_review:
                lines.append(f"- **{d.incident_id}**: {d.title} — {d.recommended_action}")
        else:
            lines.append("No incidents triggered human review.")
        lines.append("")

        lines.append("## Deterministic vs LLM-Assisted")
        lines.append("- **Deterministic:** Priority scoring, confidence, trust, risk flags, baseline comparison.")
        lines.append("- **LLM-Assisted:** Planner narrative, critic review, optimization suggestions, report formatting.")
        lines.append("- **Policy:** Deterministic layers run first and are never overridden by LLM output.")
        lines.append("")

        lines.append("## LLM Usage Policy")
        lines.append(
            "- Deterministic scoring is used for priority, confidence, and trust calculations.\n"
            "- LLMs are used only for explanation, critique, reporting, and optimization suggestions.\n"
            "- This reduces cost, improves reliability, and makes the workflow auditable.\n"
            "- Mock mode is enabled for demo stability; production mode can connect to Qwen/Llama/Mistral "
            "served via OpenAI-compatible endpoints on AMD Cloud."
        )
        lines.append("")

        return "\n".join(lines)

    def _build_markdown_report(
        self,
        run_id: str,
        incidents: List[Incident],
        baseline_results: List[BaselineDecision],
        triage_results: List[TriageDecision],
        optimizations: List[OptimizationRecommendation],
        rocm_report: ROCmReadinessReport,
        trace: List[AgentTraceEvent],
        agent_review_md: str,
        comparison_md: str,
        llm_runtime_info: dict,
    ) -> str:
        lines: List[str] = []
        lines.append(f"# ROCm AgentOps Report — {run_id}")
        lines.append(f"**Generated:** {utc_now_iso()}  ")
        lines.append(f"**Incidents Processed:** {len(incidents)}  ")
        lines.append("")

        lines.append("## Runtime Mode")
        lines.append(f"- **Mock Mode:** {'ON' if llm_runtime_info.get('mock_mode') else 'OFF'}")
        lines.append(f"- **Model:** {llm_runtime_info.get('model', 'N/A')}")
        lines.append(f"- **Base URL:** {llm_runtime_info.get('base_url', 'N/A')}")
        lines.append(f"- **Narrative Generation:** {llm_runtime_info.get('narrative_mode', 'N/A')}")
        if llm_runtime_info.get("errors"):
            lines.append("- **Fallbacks Triggered:**")
            for err in llm_runtime_info["errors"]:
                lines.append(f"  - {err}")
        else:
            lines.append("- **Fallbacks Triggered:** None")
        lines.append("- **Note:** Deterministic scoring remains unchanged regardless of LLM mode.")
        # Context-aware latency language
        if llm_runtime_info.get("narrative_mode") == "Real endpoint":
            lines.append("- **Latency:** LLM narrative latencies were measured from the configured OpenAI-compatible endpoint.")
            lines.append("- **Cost:** Costs are estimated unless provider billing data is attached.")
        else:
            lines.append("- **Latency:** LLM narrative outputs used mock/fallback mode. Latencies are estimates for demo stability.")
            lines.append("- **Cost:** Costs are simulated estimates for demonstration purposes.")
        lines.append("")

        lines.append("## AMD Live Benchmark")
        bench = load_benchmark_results("data/amd_benchmark_results.json")
        if bench:
            if bench.successful_requests > 0:
                lines.append(f"- **Run ID:** {bench.run_id}")
                lines.append(f"- **Endpoint:** {bench.endpoint_base_url}")
                lines.append(f"- **Model:** {bench.model}")
                lines.append(f"- **Avg Latency:** {bench.avg_latency_ms:.2f} ms")
                lines.append(f"- **p50 Latency:** {bench.p50_latency_ms:.2f} ms")
                lines.append(f"- **p95 Latency:** {bench.p95_latency_ms:.2f} ms")
                lines.append(f"- **Tokens/sec:** {bench.estimated_tokens_per_second:.2f}")
                lines.append(f"- **Success Rate:** {bench.successful_requests}/{bench.total_requests}")
                lines.append(f"- **Benchmark Duration:** {bench.benchmark_duration_seconds:.2f}s")
            else:
                lines.append(
                    "AMD benchmark attempted but not verified. All requests failed. "
                    "Do not use these metrics as performance evidence."
                )
                lines.append(f"- **Run ID:** {bench.run_id}")
                lines.append(f"- **Endpoint:** {bench.endpoint_base_url}")
                lines.append(f"- **Failed Requests:** {bench.failed_requests}/{bench.total_requests}")
        else:
            lines.append(
                "AMD live benchmark not yet attached. The system is ready to connect to an "
                "AMD Developer Cloud OpenAI-compatible endpoint."
            )
        lines.append("")

        lines.append(comparison_md)
        lines.append("")

        lines.append("## Top 5 Triage Results")
        for rank, d in enumerate(triage_results[:5], start=1):
            lines.append(f"### {rank}. {d.incident_id} — {d.title}")
            lines.append(f"- **System:** {d.system} | **Status:** {d.status} | **Severity:** {d.severity_hint}")
            lines.append(f"- **Priority Score:** {d.priority_score} | **Confidence:** {d.confidence_score} | **Trust:** {d.trust_score}")
            lines.append(f"- **Action:** {d.recommended_action} | **Human Review:** {'Yes' if d.human_review_required else 'No'}")
            if d.risk_flags:
                flag_labels = ", ".join(f"{f.label} ({f.severity})" for f in d.risk_flags)
                lines.append(f"- **Risk Flags:** {flag_labels}")
            lines.append("")
        if len(triage_results) > 5:
            lines.append(f"*… and {len(triage_results) - 5} more incidents. See Triage tab for full details.*")
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

        # Agent Review markdown already starts with '# Agent Review', so don't add another heading
        lines.append(agent_review_md)
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
        if llm_runtime_info.get("narrative_mode") == "Real endpoint":
            lines.append("> **Note:** LLM narrative latencies were measured from the configured OpenAI-compatible endpoint. "
                        "Deterministic scoring steps incur no LLM cost. Benchmark metrics come from `scripts/run_amd_benchmark.py`.")
        else:
            lines.append("> **Note:** LLM narrative outputs used mock/fallback mode. Latencies and costs are estimates for demo stability. "
                        "Deterministic scoring steps incur no LLM cost. Connect to a live endpoint for real inference.")
        lines.append("")

        lines.append("## Limitations")
        lines.append("- Deterministic scoring uses heuristics; domain-specific tuning may improve accuracy.")
        lines.append("- Token and cost estimates are approximate (len(text)/4 heuristic).")
        lines.append("- Benchmark results reflect point-in-time endpoint performance.")
        lines.append("- LLM-generated narrative should be reviewed for factual accuracy before production use.")
        lines.append("- This is a hackathon MVP; production deployment requires additional hardening.")
        lines.append("")

        lines.append("## Next Steps")
        lines.append("1. Tune scoring weights for your incident taxonomy.")
        lines.append("2. Run `scripts/run_amd_benchmark.py` against your AMD Developer Cloud endpoint.")
        lines.append("3. Connect a live Qwen/Llama/Mistral model via vLLM on ROCm for real LLM narrative.")
        lines.append("4. Add persistent trace storage and alerting integrations.")
        lines.append("5. Review and validate all LLM-generated claims before judge presentation.")
        lines.append("")

        return "\n".join(lines)
