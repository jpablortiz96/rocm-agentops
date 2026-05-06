"""Incident Triage Workflow: orchestrates deterministic scoring end-to-end."""

from __future__ import annotations

from typing import List, Optional

from agents.critic_agent import CriticAgent
from agents.optimizer_agent import OptimizerAgent
from agents.planner_agent import PlannerAgent
from agents.rocm_advisor_agent import ROCmAdvisorAgent
from core.audit_seal import generate_audit_seal
from core.benchmark_schemas import AmdBenchmarkSummary
from core.benchmarking import load_benchmark_results, load_preferred_benchmark_results
from core.escalation import generate_escalation_packets
from core.llm_client import LLMClient, llm
from core.model_router import (
    LARGE_MODEL_NAME,
    SMALL_MODEL_NAME,
    build_model_profiles,
    route_incidents,
)
from core.policy_engine import (
    apply_policy_hits_to_routes,
    evaluate_policy_compliance,
    load_policy_configuration,
)
from core.schemas import (
    AgentRunResult,
    AgentTraceEvent,
    AuditSeal,
    BaselineDecision,
    EscalationPacket,
    HistoricalRoutingAnalytics,
    Incident,
    ModelRouteDecision,
    OptimizationRecommendation,
    PolicyComplianceSummary,
    ROCmReadinessReport,
    SLAMonitorResult,
    TelemetryCard,
    TriageDecision,
    WorkflowStrategyResult,
)
from core.scoring import calculate_incident_priority_score, run_baseline_triage
from core.strategy_simulator import evaluate_sla_monitor, simulate_workflow_strategies
from core.telemetry_card import generate_telemetry_card
from core.tracing import create_run_id, elapsed_ms, make_trace_event, start_timer, utc_now_iso
from core.war_room_packet import build_war_room_packet


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
        benchmark_summary = load_preferred_benchmark_results()
        small_model_benchmark = load_benchmark_results("data/amd_benchmark_results_qwen15b.json")
        policy_configuration = load_policy_configuration()
        policy_thresholds = dict(policy_configuration.get("thresholds", {}))
        incidents_by_id = {incident.id: incident for incident in incidents}

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

        t2 = start_timer()
        triage_results: List[TriageDecision] = []
        for incident in incidents:
            score = calculate_incident_priority_score(incident)
            triage_results.append(
                TriageDecision(
                    incident_id=incident.id,
                    title=incident.title,
                    system=incident.system,
                    status=incident.status.value,
                    severity_hint=incident.severity_hint.value,
                    priority_score=score["priority_score"],
                    confidence_score=score["confidence_score"],
                    trust_score=score["trust_score"],
                    recommended_action=score["recommended_action"],
                    reasons=score["reasons"],
                    risk_flags=score["risk_flags"],
                    human_review_required=score["human_review_required"],
                )
            )

        triage_results.sort(key=lambda decision: decision.priority_score, reverse=True)
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

        t3 = start_timer()
        planner_text = self.planner.generate_plan_text(len(incidents))
        planner_meta = self.planner.last_llm_meta or {}
        any_llm_used, any_mock_used = _record_llm_meta(
            planner_meta, llm_errors, any_llm_used, any_mock_used
        )
        trace.append(
            make_trace_event(
                run_id=run_id,
                agent_name="planner",
                step_name="plan_generated",
                input_summary=f"{len(incidents)} incidents",
                output_summary=_llm_output_summary(planner_meta),
                latency_ms=elapsed_ms(t3),
                status="success",
                estimated_tokens=planner_meta.get("estimated_input_tokens", 0)
                + planner_meta.get("estimated_output_tokens", 0),
                estimated_cost_usd=planner_meta.get("estimated_cost_usd", 0.0),
            )
        )

        t4 = start_timer()
        critic_text = self.critic.review_batch(triage_results)
        critic_meta = self.critic.last_llm_meta or {}
        any_llm_used, any_mock_used = _record_llm_meta(
            critic_meta, llm_errors, any_llm_used, any_mock_used
        )
        trace.append(
            make_trace_event(
                run_id=run_id,
                agent_name="critic",
                step_name="critic_review",
                input_summary=f"Reviewed {len(triage_results)} decisions",
                output_summary=_llm_output_summary(critic_meta),
                latency_ms=elapsed_ms(t4),
                status="success",
                estimated_tokens=critic_meta.get("estimated_input_tokens", 0)
                + critic_meta.get("estimated_output_tokens", 0),
                estimated_cost_usd=critic_meta.get("estimated_cost_usd", 0.0),
            )
        )

        t5 = start_timer()
        optimizations = self.optimizer.optimize_batch(triage_results)
        optimizer_meta = self.optimizer.last_llm_meta or {}
        any_llm_used, any_mock_used = _record_llm_meta(
            optimizer_meta, llm_errors, any_llm_used, any_mock_used
        )
        trace.append(
            make_trace_event(
                run_id=run_id,
                agent_name="optimizer",
                step_name="optimization_recommendations",
                input_summary=f"Analyzed {len(triage_results)} triage decisions",
                output_summary=_llm_output_summary(optimizer_meta),
                latency_ms=elapsed_ms(t5),
                status="success",
                estimated_tokens=optimizer_meta.get("estimated_input_tokens", 0)
                + optimizer_meta.get("estimated_output_tokens", 0),
                estimated_cost_usd=optimizer_meta.get("estimated_cost_usd", 0.0),
            )
        )

        t6 = start_timer()
        rocm_report = self.rocm_advisor.advise_batch(incidents)
        rocm_meta = self.rocm_advisor.last_llm_meta or {}
        any_llm_used, any_mock_used = _record_llm_meta(
            rocm_meta, llm_errors, any_llm_used, any_mock_used
        )
        trace.append(
            make_trace_event(
                run_id=run_id,
                agent_name="rocm_advisor",
                step_name="rocm_readiness_check",
                input_summary="Evaluated ROCm relevance",
                output_summary=_llm_output_summary(rocm_meta),
                latency_ms=elapsed_ms(t6),
                status="success",
                estimated_tokens=rocm_meta.get("estimated_input_tokens", 0)
                + rocm_meta.get("estimated_output_tokens", 0),
                estimated_cost_usd=rocm_meta.get("estimated_cost_usd", 0.0),
            )
        )

        comparison_md = self._build_comparison_markdown(baseline_results, triage_results)
        mismatch_insights = self._generate_mismatch_insights(baseline_results, triage_results)
        agent_review_md = self._build_agent_review_markdown(
            planner_text, critic_text, mismatch_insights, triage_results
        )

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

        t7 = start_timer()
        strategy_results = simulate_workflow_strategies(
            triage_results,
            current_benchmark=benchmark_summary,
            small_model_benchmark=small_model_benchmark,
        )
        recommended_strategy = _pick_recommended_strategy(strategy_results)
        model_routes = route_incidents(
            triage_results,
            incidents_by_id,
            strategy_name=recommended_strategy.strategy_name if recommended_strategy else "Balanced AMD Router",
            current_benchmark=benchmark_summary,
            small_model_benchmark=small_model_benchmark,
        )
        sla_monitor_result = evaluate_sla_monitor(
            recommended_strategy or _fallback_strategy_result(),
            benchmark_summary,
            triage_results,
            fallback_count=len(llm_errors),
            max_p95_latency_ms=float(policy_thresholds.get("p95_latency_ms", 2500.0)),
            min_trust_score=float(
                policy_thresholds.get("minimum_trust_score_autonomous_action", 60.0)
            ),
        )
        policy_compliance = evaluate_policy_compliance(
            triage_results,
            model_routes,
            sla_monitor_result,
            benchmark_summary=benchmark_summary,
            policy_configuration=policy_configuration,
        )
        model_routes = apply_policy_hits_to_routes(model_routes, policy_compliance)
        historical_analytics = self._build_historical_routing_analytics(
            model_routes,
            benchmark_summary,
            small_model_benchmark,
        )
        predicted_escalation_count = sum(
            1 for decision in triage_results if decision.human_review_required
        )
        command_center_summary = self._build_command_center_summary(
            recommended_strategy,
            model_routes,
            sla_monitor_result,
            predicted_escalation_count,
        )
        telemetry_card = generate_telemetry_card(
            workflow_run_id=run_id,
            benchmark_summary=benchmark_summary,
            llm_runtime_info=llm_runtime_info,
            triage_decisions=triage_results,
            model_routes=model_routes,
            mismatch_insights=mismatch_insights,
        )
        trace.append(
            make_trace_event(
                run_id=run_id,
                agent_name="command_center",
                step_name="workflow_compiled",
                input_summary=f"{len(triage_results)} triage decisions",
                output_summary=(
                    f"Recommended strategy: {recommended_strategy.strategy_name if recommended_strategy else 'none'}; "
                    f"human review packets: {predicted_escalation_count}; "
                    f"policy status: {policy_compliance.compliance_status}"
                ),
                latency_ms=elapsed_ms(t7),
                status="success",
                estimated_tokens=0,
                estimated_cost_usd=0.0,
            )
        )

        t8 = start_timer()
        report_generated_at = utc_now_iso()
        trace.append(
            make_trace_event(
                run_id=run_id,
                agent_name="reporter",
                step_name="final_report_assembled",
                input_summary="Finalizing report artifacts",
                output_summary=(
                    f"Run {run_id} finalized for {len(incidents)} incidents "
                    f"with {len(trace) + 1} trace events."
                ),
                latency_ms=elapsed_ms(t8),
                status="success",
                estimated_tokens=0,
                estimated_cost_usd=0.0,
            )
        )
        audit_payload = self._build_audit_payload(
            run_id=run_id,
            incidents=incidents,
            triage_results=triage_results,
            trace=trace,
            benchmark_summary=benchmark_summary,
            llm_runtime_info=llm_runtime_info,
            model_routes=model_routes,
            recommended_strategy=recommended_strategy,
            policy_compliance=policy_compliance,
        )
        audit_seal = generate_audit_seal(
            audit_payload,
            generated_at=report_generated_at,
        )
        escalation_packets = generate_escalation_packets(
            triage_results,
            incidents_by_id,
            run_id=run_id,
            audit_id=audit_seal.audit_id,
            benchmark_summary=benchmark_summary,
            llm_runtime_info=llm_runtime_info,
            incident_policy_hits=policy_compliance.incident_policy_hits,
        )
        result = AgentRunResult(
            run_id=run_id,
            triage_results=triage_results,
            baseline_results=baseline_results,
            trace=trace,
            optimizations=optimizations,
            rocm_report=rocm_report,
            agent_review_markdown=agent_review_md,
            comparison_markdown=comparison_md,
            final_report_markdown="",
            llm_runtime_info=llm_runtime_info,
            command_center_summary=command_center_summary,
            model_routes=model_routes,
            strategy_results=strategy_results,
            recommended_strategy=recommended_strategy,
            sla_monitor_result=sla_monitor_result,
            policy_compliance=policy_compliance,
            historical_analytics=historical_analytics,
            escalation_packets=escalation_packets,
            audit_seal=audit_seal,
            telemetry_card=telemetry_card,
        )
        result.final_report_markdown = self._build_markdown_report(
            run_id=result.run_id,
            generated_at=report_generated_at,
            incidents=incidents,
            baseline_results=baseline_results,
            triage_results=triage_results,
            optimizations=optimizations,
            rocm_report=rocm_report,
            trace=trace,
            comparison_md=comparison_md,
            mismatch_insights=mismatch_insights,
            llm_runtime_info=llm_runtime_info,
            benchmark_summary=benchmark_summary,
            command_center_summary=command_center_summary,
            model_routes=model_routes,
            strategy_results=strategy_results,
            recommended_strategy=recommended_strategy,
            sla_monitor_result=sla_monitor_result,
            escalation_packets=escalation_packets,
            audit_seal=audit_seal,
            telemetry_card=telemetry_card,
        )
        result.war_room_packet = build_war_room_packet(result, benchmark_summary=benchmark_summary)
        return result

    def _build_comparison_markdown(
        self, baseline: List[BaselineDecision], agentops: List[TriageDecision]
    ) -> str:
        lines: List[str] = [
            "## Baseline vs ROCm AgentOps",
            "",
            "| Capability | Baseline Agent | ROCm AgentOps |",
            "|---|---|---|",
            "| Priority ranking | Yes | Yes |",
            "| Trust score | No | Yes |",
            "| Risk flags | No | Yes |",
            "| Human review escalation | No | Yes |",
            "| Trace replay | No | Yes |",
            "| Cost estimate | No | Yes |",
            "| Latency visibility | No | Yes |",
            "| Optimization recommendations | No | Yes |",
            "| AMD/ROCm readiness | No | Yes |",
            "| Final audit report | No | Yes |",
            "",
            "**Metric Snapshot**",
        ]

        top_baseline = baseline[0] if baseline else None
        top_agentops = agentops[0] if agentops else None
        human_review_count = sum(1 for decision in agentops if decision.human_review_required)

        if top_baseline:
            lines.append(
                f"- **Highest Baseline Priority:** {top_baseline.incident_id} - {top_baseline.title} (score: {top_baseline.baseline_score})"
            )
        if top_agentops:
            lines.append(
                f"- **Highest AgentOps Priority:** {top_agentops.incident_id} - {top_agentops.title} (score: {top_agentops.priority_score})"
            )
        lines.append(f"- **High-Risk Incidents Requiring Human Review:** {human_review_count}")
        lines.append("")
        return "\n".join(lines)

    def _generate_mismatch_insights(
        self, baseline: List[BaselineDecision], agentops: List[TriageDecision]
    ) -> List[str]:
        insights: List[str] = []
        baseline_rank = {decision.incident_id: decision.baseline_rank for decision in baseline}
        agentops_rank = {decision.incident_id: index + 1 for index, decision in enumerate(agentops)}

        if baseline_rank.get("INC-004") and agentops_rank.get("INC-004"):
            if baseline_rank["INC-004"] > agentops_rank["INC-004"]:
                insights.append(
                    "**INC-004** (Suspicious IAM activity) was under-ranked by the baseline because it only affects 5 users. "
                    "AgentOps elevated it to top-3 due to critical security severity, empty evidence, and urgent 10-minute SLA."
                )

        if baseline_rank.get("INC-005") and agentops_rank.get("INC-005"):
            if baseline_rank["INC-005"] < agentops_rank["INC-005"]:
                insights.append(
                    "**INC-005** (Notification delay) was over-ranked by the baseline because it affects 250,000 users. "
                    "AgentOps correctly deprioritized it: low severity, mitigated status, and minimal revenue impact."
                )

        if baseline_rank.get("INC-007") and agentops_rank.get("INC-007"):
            if baseline_rank["INC-007"] > agentops_rank["INC-007"]:
                insights.append(
                    "**INC-007** (LLM hallucination) was under-ranked by the baseline. "
                    "AgentOps elevated it because hallucination risk is a critical AI-safety issue requiring human review."
                )

        if baseline_rank.get("INC-006") and agentops_rank.get("INC-006"):
            if baseline_rank["INC-006"] > agentops_rank["INC-006"]:
                insights.append(
                    "**INC-006** (GPU inference degradation on MI300X) was under-ranked by the baseline. "
                    "AgentOps elevated it because AMD/ROCm inference stack degradation affects model serving reliability."
                )

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
        lines: List[str] = [
            "# Agent Review",
            "",
            "## Planner Output",
            planner_text,
            "",
            "## Critic Output",
            critic_text,
            "",
            "## Baseline Mismatch Insights",
        ]

        if mismatch_insights:
            lines.extend(f"- {insight}" for insight in mismatch_insights)
        else:
            lines.append("No significant baseline mismatches detected.")

        lines.extend(["", "## Human Review Triggers"])
        human_review = [decision for decision in triage_results if decision.human_review_required]
        if human_review:
            lines.append(f"{len(human_review)} incident(s) triggered human review:")
            lines.extend(
                f"- **{decision.incident_id}**: {decision.title} - {decision.recommended_action}"
                for decision in human_review
            )
        else:
            lines.append("No incidents triggered human review.")

        lines.extend(
            [
                "",
                "## Deterministic vs LLM-Assisted",
                "- **Deterministic:** Priority scoring, confidence, trust, risk flags, baseline comparison.",
                "- **LLM-Assisted:** Planner narrative, critic review, optimization suggestions, report formatting.",
                "- **Policy:** Deterministic layers run first and are never overridden by LLM output.",
                "",
                "## LLM Usage Policy",
                "- Deterministic scoring is used for priority, confidence, and trust calculations.",
                "- LLMs are used only for explanation, critique, reporting, and optimization suggestions.",
                "- This reduces cost, improves reliability, and makes the workflow auditable.",
                "- Mock mode remains available for runtime resilience; production mode can connect to Qwen/Llama/Mistral served via OpenAI-compatible endpoints on AMD Cloud.",
                "",
            ]
        )
        return "\n".join(lines)

    def _build_command_center_summary(
        self,
        recommended_strategy: Optional[WorkflowStrategyResult],
        model_routes: List[ModelRouteDecision],
        sla_monitor_result: Optional[SLAMonitorResult],
        escalation_packet_count: int,
    ) -> str:
        deterministic_count = sum(
            1 for route in model_routes if route.selected_execution_mode == "deterministic_only"
        )
        small_model_count = sum(
            1 for route in model_routes if route.selected_execution_mode == "small_model"
        )
        large_model_count = sum(
            1 for route in model_routes if route.selected_execution_mode == "large_model"
        )
        human_review_count = sum(
            1 for route in model_routes if route.selected_execution_mode == "human_review"
        )
        qwen15_summary_count = sum(
            1 for route in model_routes if route.recommended_model == SMALL_MODEL_NAME
        )
        qwen7_critique_count = sum(
            1 for route in model_routes if route.recommended_model == LARGE_MODEL_NAME
        )
        strategy_name = recommended_strategy.strategy_name if recommended_strategy else "Balanced AMD Router"
        sla_status = sla_monitor_result.status if sla_monitor_result else "WARN"

        return "\n".join(
            [
                "ROCm AgentOps compiles the workflow into deterministic, small-model, large-model, and human-review steps based on risk, trust, SLA, and benchmark evidence.",
                "",
                f"- **Recommended strategy:** {strategy_name}",
                (
                    f"- **Execution plan:** {deterministic_count} deterministic-only, {small_model_count} small-model, "
                    f"{large_model_count} large-model, {human_review_count} human-review routes."
                ),
                (
                    f"- **Model-assisted actions:** {qwen15_summary_count} Qwen 1.5B summaries, "
                    f"{qwen7_critique_count} Qwen 7B critical/ROCm critiques, {human_review_count} human-review gates."
                ),
                f"- **SLA status:** {sla_status}",
                f"- **Escalation packets ready:** {escalation_packet_count}",
            ]
        )

    def _build_audit_payload(
        self,
        *,
        run_id: str,
        incidents: List[Incident],
        triage_results: List[TriageDecision],
        trace: List[AgentTraceEvent],
        benchmark_summary: Optional[AmdBenchmarkSummary],
        llm_runtime_info: dict,
        model_routes: List[ModelRouteDecision],
        recommended_strategy: Optional[WorkflowStrategyResult],
        policy_compliance: PolicyComplianceSummary,
    ) -> dict:
        return {
            "run_id": run_id,
            "incidents_processed": [incident.model_dump(mode="json") for incident in incidents],
            "triage_decisions": [decision.model_dump(mode="json") for decision in triage_results],
            "trace_events": [event.model_dump(mode="json") for event in trace],
            "model_routes": [route.model_dump(mode="json") for route in model_routes],
            "policy_compliance": policy_compliance.model_dump(mode="json"),
            "benchmark_summary": benchmark_summary.model_dump(mode="json") if benchmark_summary else None,
            "runtime_mode": llm_runtime_info,
            "recommended_strategy": recommended_strategy.model_dump(mode="json") if recommended_strategy else None,
        }

    def _build_markdown_report(
        self,
        *,
        run_id: str,
        generated_at: str,
        incidents: List[Incident],
        baseline_results: List[BaselineDecision],
        triage_results: List[TriageDecision],
        optimizations: List[OptimizationRecommendation],
        rocm_report: Optional[ROCmReadinessReport],
        trace: List[AgentTraceEvent],
        comparison_md: str,
        mismatch_insights: List[str],
        llm_runtime_info: dict,
        benchmark_summary: Optional[AmdBenchmarkSummary],
        command_center_summary: str,
        model_routes: List[ModelRouteDecision],
        strategy_results: List[WorkflowStrategyResult],
        recommended_strategy: Optional[WorkflowStrategyResult],
        sla_monitor_result: Optional[SLAMonitorResult],
        escalation_packets: List[EscalationPacket],
        audit_seal: AuditSeal,
        telemetry_card: TelemetryCard,
    ) -> str:
        lines: List[str] = [
            f"# ROCm AgentOps Report - {run_id}",
            f"**Generated:** {generated_at}  ",
            f"**Incidents Processed:** {len(incidents)}  ",
            "",
            "## Runtime Mode",
            f"- **Mock Mode:** {'ON' if llm_runtime_info.get('mock_mode') else 'OFF'}",
            f"- **Model:** {llm_runtime_info.get('model', 'N/A')}",
            f"- **Base URL:** {llm_runtime_info.get('base_url', 'N/A')}",
            f"- **Narrative Generation:** {llm_runtime_info.get('narrative_mode', 'N/A')}",
        ]

        if llm_runtime_info.get("errors"):
            lines.append("- **Fallbacks Triggered:**")
            lines.extend(f"  - {error}" for error in llm_runtime_info["errors"])
        else:
            lines.append("- **Fallbacks Triggered:** None")

        lines.append("- **Note:** Deterministic scoring remains unchanged regardless of LLM mode.")
        if llm_runtime_info.get("narrative_mode") == "Real endpoint":
            lines.append("- **Latency:** LLM narrative latencies were measured from the configured OpenAI-compatible endpoint.")
            lines.append("- **Cost:** Costs are estimated unless provider billing data is attached.")
        else:
            lines.append("- **Latency:** LLM narrative outputs used mock/fallback mode. Latencies are estimates for runtime resilience when a live endpoint is unavailable.")
            lines.append("- **Cost:** Costs are estimated because provider billing data is not attached in this run.")

        lines.extend(["", "## AMD Live Benchmark"])
        if _benchmark_is_verified(benchmark_summary):
            artifact_source_line = (
                "- **Artifact Source:** Bundled example benchmark artifact"
                if benchmark_summary.artifact_origin == "example"
                else "- **Artifact Source:** Submitted benchmark artifact"
            )
            lines.extend(
                [
                    artifact_source_line,
                    f"- **Run ID:** {benchmark_summary.run_id}",
                    f"- **Endpoint:** {benchmark_summary.endpoint_base_url}",
                    f"- **Model:** {benchmark_summary.model}",
                    f"- **Avg Latency:** {benchmark_summary.avg_latency_ms:.2f} ms",
                    f"- **p50 Latency:** {benchmark_summary.p50_latency_ms:.2f} ms",
                    f"- **p95 Latency:** {benchmark_summary.p95_latency_ms:.2f} ms",
                    f"- **Tokens/sec:** {benchmark_summary.estimated_tokens_per_second:.2f}",
                    f"- **Success Rate:** {benchmark_summary.successful_requests}/{benchmark_summary.total_requests}",
                    f"- **Benchmark Duration:** {benchmark_summary.benchmark_duration_seconds:.2f}s",
                ]
            )
        elif benchmark_summary:
            lines.extend(
                [
                    "AMD benchmark attempted but not verified. All requests failed.",
                    (
                        "- **Artifact Source:** Bundled example benchmark artifact"
                        if benchmark_summary.artifact_origin == "example"
                        else "- **Artifact Source:** Submitted benchmark artifact"
                    ),
                    f"- **Run ID:** {benchmark_summary.run_id}",
                    f"- **Endpoint:** {benchmark_summary.endpoint_base_url}",
                    f"- **Failed Requests:** {benchmark_summary.failed_requests}/{benchmark_summary.total_requests}",
                ]
            )
        else:
            lines.append(
                "AMD live benchmark not yet attached. The system is ready to connect to an AMD Developer Cloud OpenAI-compatible endpoint."
            )

        lines.extend(["", comparison_md, "", "## Top 5 Triage Results"])
        for rank, decision in enumerate(triage_results[:5], start=1):
            lines.extend(
                [
                    f"### {rank}. {decision.incident_id} - {decision.title}",
                    f"- **System:** {decision.system} | **Status:** {decision.status} | **Severity:** {decision.severity_hint}",
                    f"- **Priority Score:** {decision.priority_score} | **Confidence:** {decision.confidence_score} | **Trust:** {decision.trust_score}",
                    f"- **Action:** {decision.recommended_action} | **Human Review:** {'Yes' if decision.human_review_required else 'No'}",
                ]
            )
            if decision.risk_flags:
                flag_labels = ", ".join(f"{flag.label} ({flag.severity})" for flag in decision.risk_flags)
                lines.append(f"- **Risk Flags:** {flag_labels}")
            lines.append("")
        if len(triage_results) > 5:
            lines.append(f"*... and {len(triage_results) - 5} more incidents. See the Triage tab for full details.*")
            lines.append("")

        lines.append("## Human Review Triggers")
        human_review_lines = [
            f"- **{decision.incident_id}**: {decision.title} ({decision.trust_score} trust)"
            for decision in triage_results
            if decision.human_review_required
        ]
        lines.extend(human_review_lines or ["- No incidents triggered human review."])
        lines.extend(["", "## Baseline Mismatch Insights"])
        if mismatch_insights:
            lines.extend(f"- {insight}" for insight in mismatch_insights)
        else:
            lines.append("- No material ranking mismatches were detected in this run.")
        lines.extend(
            [
                "",
                "## Command Center Summary",
                command_center_summary,
                "",
                "## Model Router Decisions",
                "- `Human review packet only` means no model generation is required before human ownership.",
                "- Deterministic/template estimates are local workflow timing estimates, not model inference latency.",
            ]
        )
        lines.extend(self._build_model_router_report_lines(model_routes))

        lines.extend(["", "## Strategy Comparison"])
        for strategy in strategy_results:
            lines.append(
                f"- **{strategy.strategy_name}**: {strategy.total_estimated_latency_ms:.0f} ms total latency, "
                f"{strategy.estimated_cost_usd:.4f} USD estimated cost, {strategy.expected_quality_score:.1f} quality, "
                f"{strategy.risk_coverage_score:.1f} coverage, {strategy.human_review_count} human reviews, "
                f"{strategy.model_calls} model calls. {'Recommended.' if strategy.recommended else ''}"
            )

        lines.extend(["", "## SLA Monitor"])
        if sla_monitor_result:
            lines.append(f"- **Status:** {sla_monitor_result.status}")
            if sla_monitor_result.summary_message:
                lines.append(f"- **Message:** {sla_monitor_result.summary_message}")
            if sla_monitor_result.violations:
                lines.append("- **Violations:**")
                lines.extend(f"  - {violation}" for violation in sla_monitor_result.violations)
            else:
                lines.append("- **Violations:** None")
            lines.append("- **Recommended Mitigation:**")
            lines.extend(f"  - {item}" for item in sla_monitor_result.recommended_mitigation)
        else:
            lines.append("- SLA monitor not generated.")

        lines.extend(["", "## Escalation Packets"])
        if escalation_packets:
            lines.extend(
                f"- **{packet.incident_id}** -> {packet.recipient_email} | `{packet.subject}`"
                for packet in escalation_packets
            )
        else:
            lines.append("- No escalation packets generated.")

        lines.extend(
            [
                "",
                "## Audit Seal",
                f"- **Audit ID:** {audit_seal.audit_id}",
                f"- **SHA-256:** `{audit_seal.sha256}`",
                f"- **Generated At:** {audit_seal.generated_at}",
                f"- **Included Fields:** {', '.join(audit_seal.included_fields)}",
                f"- **Explanation:** {audit_seal.explanation}",
                "",
                "## Telemetry Card Summary",
                f"- **Title:** {telemetry_card.title}",
                f"- **Workflow Run ID:** {telemetry_card.workflow_run_id}",
                f"- **Benchmark Run ID:** {telemetry_card.benchmark_run_id}",
                f"- **Model:** {telemetry_card.model}",
                f"- **Success Rate:** {telemetry_card.success_rate:.2%}",
                f"- **p50 / p95:** {telemetry_card.p50_latency_ms:.2f} ms / {telemetry_card.p95_latency_ms:.2f} ms",
                f"- **Tokens/sec:** {telemetry_card.tokens_per_second:.2f}",
                f"- **Suggested Post:** Prepared under 900 characters with {' '.join(telemetry_card.hashtags)}.",
                "",
                "## Optimization Recommendations",
            ]
        )
        for optimization in optimizations:
            lines.extend(
                [
                    f"### {optimization.title}",
                    f"- **Category:** {optimization.category} | **Impact:** {optimization.estimated_impact} | **Complexity:** {optimization.complexity}",
                ]
            )
            if optimization.description:
                lines.append(f"- **Description:** {optimization.description}")
            if optimization.recommendation:
                lines.append(f"- **Recommendation:** {optimization.recommendation}")
            if optimization.expected_benefit:
                lines.append(f"- **Expected Benefit:** {optimization.expected_benefit}")
            if optimization.action_items:
                lines.append("- **Actions:**")
                lines.extend(f"  - {item}" for item in optimization.action_items)
            lines.append("")

        lines.append("## ROCm / AMD Readiness")
        if rocm_report:
            lines.append(f"**Summary:** {rocm_report.summary}")
            lines.append(f"**Estimated Impact:** {rocm_report.estimated_impact}")
            if rocm_report.gpu_relevant_steps:
                lines.append(f"**GPU Relevant Steps:** {', '.join(rocm_report.gpu_relevant_steps)}")
            if rocm_report.rocm_optimizations:
                lines.append("**ROCm Optimizations:**")
                lines.extend(f"- {item}" for item in rocm_report.rocm_optimizations)
            if rocm_report.batching_opportunities:
                lines.append("**Batching Opportunities:**")
                lines.extend(f"- {item}" for item in rocm_report.batching_opportunities)
            if rocm_report.limitations:
                lines.append("**Limitations:**")
                lines.extend(f"- {item}" for item in rocm_report.limitations)
        else:
            lines.append("No ROCm readiness report generated.")

        lines.extend(["", "## Trace Summary", f"Workflow executed with run ID `{run_id}`.", "", "| Step | Agent | Latency (ms) | Est. Tokens | Est. Cost |", "|------|-------|-------------:|------------:|----------:|"])
        for event in trace:
            lines.append(
                f"| {event.step_name} | {event.agent_name} | {event.latency_ms:.2f} | {event.estimated_tokens} | ${event.estimated_cost_usd:.4f} |"
            )

        if llm_runtime_info.get("narrative_mode") == "Real endpoint":
            lines.extend(
                [
                    "",
                    "> **Note:** LLM narrative latencies were measured from the configured OpenAI-compatible endpoint. "
                    "Deterministic scoring steps incur no LLM cost. Benchmark metrics were captured by the AMD/vLLM benchmark harness.",
                ]
            )
        else:
            lines.extend(
                [
                    "",
                    "> **Note:** LLM narrative outputs used mock/fallback mode. Latencies and costs are estimates for runtime resilience. "
                    "Deterministic scoring steps incur no LLM cost. Connect to a live endpoint for real inference.",
                ]
            )

        lines.extend(
            [
                "",
                "## Limitations",
                "- Deterministic scoring uses configurable heuristics and should be calibrated against each organization's incident taxonomy.",
                "- Token and cost values are estimates unless connected to provider billing or metering data.",
                "- Benchmark results reflect point-in-time endpoint performance and should be refreshed after infrastructure changes.",
                "- LLM-generated narrative is advisory; deterministic scores, risk flags, and human approvals remain the source of operational control.",
                "- Production deployment should add persistent storage, authentication, access control, and alerting integrations.",
                "",
                "## Recommended Operational Actions",
                "1. Review and acknowledge all human-review escalation packets.",
                "2. Assign owners for critical incidents and confirm SLA response.",
                "3. Re-run the AMD/vLLM benchmark harness after model, endpoint, workload, or hardware changes.",
                "4. Update policy guardrails when routing thresholds, SLA targets, or risk tolerance change.",
                "5. Enable persistent trace storage and alerting integrations for production operations.",
                "6. Schedule periodic audit reviews using the generated audit seal and War Room Packet.",
                "",
            ]
        )

        return "\n".join(lines)

    def _build_model_router_report_lines(
        self, model_routes: List[ModelRouteDecision]
    ) -> List[str]:
        deterministic_routes = [
            route.incident_id for route in model_routes if route.selected_execution_mode == "deterministic_only"
        ]
        small_model_routes = [
            route.incident_id for route in model_routes if route.recommended_model == SMALL_MODEL_NAME
        ]
        large_model_routes = [
            route.incident_id for route in model_routes if route.recommended_model == LARGE_MODEL_NAME
        ]
        human_review_routes = [
            f"{route.incident_id} -> {route.owner_name}"
            for route in model_routes
            if route.selected_execution_mode == "human_review"
        ]
        return [
            f"- **Deterministic/template routes:** {', '.join(deterministic_routes) if deterministic_routes else 'None'}",
            f"- **Qwen 1.5B summaries:** {', '.join(small_model_routes) if small_model_routes else 'None'}",
            f"- **Qwen 7B critiques:** {', '.join(large_model_routes) if large_model_routes else 'None'}",
            f"- **Human-review gates:** {', '.join(human_review_routes) if human_review_routes else 'None'}",
        ]

    def _build_historical_routing_analytics(
        self,
        model_routes: List[ModelRouteDecision],
        benchmark_summary: Optional[AmdBenchmarkSummary],
        small_model_benchmark: Optional[AmdBenchmarkSummary],
    ) -> HistoricalRoutingAnalytics:
        total_routes = max(len(model_routes), 1)
        deterministic_count = sum(
            1 for route in model_routes if route.selected_execution_mode == "deterministic_only"
        )
        small_model_count = sum(
            1 for route in model_routes if route.selected_execution_mode == "small_model"
        )
        large_model_count = sum(
            1 for route in model_routes if route.selected_execution_mode == "large_model"
        )
        human_review_count = sum(
            1 for route in model_routes if route.selected_execution_mode == "human_review"
        )
        profiles = build_model_profiles(benchmark_summary, small_model_benchmark)
        all_large_latency = len(model_routes) * float(profiles["large_model"]["latency_ms"])
        all_large_cost = len(model_routes) * float(profiles["large_model"]["cost_usd"])
        actual_latency = sum(route.expected_latency_ms for route in model_routes)
        actual_cost = sum(route.expected_cost_usd for route in model_routes)
        latency_avoided = max(0.0, all_large_latency - actual_latency)
        cost_avoided = max(0.0, all_large_cost - actual_cost)

        return HistoricalRoutingAnalytics(
            deterministic_only_pct=round((deterministic_count / total_routes) * 100, 1),
            small_model_pct=round((small_model_count / total_routes) * 100, 1),
            large_model_pct=round((large_model_count / total_routes) * 100, 1),
            human_review_pct=round((human_review_count / total_routes) * 100, 1),
            estimated_cost_avoided_vs_all_large_model_usd=round(cost_avoided, 4),
            estimated_latency_avoided_vs_all_large_model_ms=round(latency_avoided, 2),
            summary=(
                f"Routing avoided an estimated {cost_avoided:.4f} USD and {latency_avoided:.0f} ms "
                "relative to sending every incident through Qwen 7B."
            ),
        )


def _record_llm_meta(
    llm_meta: dict,
    llm_errors: list[str],
    any_llm_used: bool,
    any_mock_used: bool,
) -> tuple[bool, bool]:
    if llm_meta.get("error"):
        llm_errors.append(str(llm_meta["error"]))
    if llm_meta.get("used_llm"):
        any_llm_used = True
    if llm_meta.get("used_mock"):
        any_mock_used = True
    return any_llm_used, any_mock_used


def _llm_output_summary(llm_meta: dict) -> str:
    if llm_meta.get("used_llm"):
        return "LLM narrative generated"
    if llm_meta.get("error"):
        return f"Mock/fallback narrative used (error: {llm_meta['error']})"
    return "Mock/fallback narrative used"


def _pick_recommended_strategy(
    strategy_results: List[WorkflowStrategyResult],
) -> Optional[WorkflowStrategyResult]:
    return next((strategy for strategy in strategy_results if strategy.recommended), None)


def _fallback_strategy_result() -> WorkflowStrategyResult:
    return WorkflowStrategyResult(
        strategy_name="Balanced AMD Router",
        description="Fallback strategy placeholder.",
        total_estimated_latency_ms=0.0,
        p95_latency_risk="unknown",
        estimated_cost_usd=0.0,
        expected_quality_score=0.0,
        risk_coverage_score=0.0,
        human_review_count=0,
        model_calls=0,
        deterministic_steps=0,
        recommended=True,
        benchmark_source="No strategy results available",
        risks=["Strategy simulation unavailable."],
        rationale="Fallback strategy used because no strategy results were generated.",
    )


def _benchmark_is_verified(summary: Optional[AmdBenchmarkSummary]) -> bool:
    return bool(summary and summary.successful_requests > 0 and summary.total_requests > 0)
