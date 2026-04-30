"""Optimizer Agent: suggests cost, latency, and accuracy improvements."""

from typing import List

from core.llm_client import LLMClient, llm
from core.schemas import AgentTrace, OptimizationRecommendation, TriageResult
from core.tracing import TraceBuilder


class OptimizerAgent:
    """Generates optimization recommendations for the agentic workflow."""

    def __init__(self, llm_client: LLMClient = llm):
        self.llm = llm_client
        self.name = "optimizer"

    def optimize(
        self,
        triage_results: List[TriageResult],
        trace: AgentTrace,
        trace_builder: TraceBuilder,
    ) -> List[OptimizationRecommendation]:
        """Produce optimization recommendations."""
        trace_builder.start_step(
            "optimize", self.name, input_summary=f"{len(triage_results)} results"
        )

        opts = []
        total_latency = sum(s.latency_ms for s in trace.steps)
        avg_conf = (
            sum(r.confidence_score for r in triage_results) / len(triage_results)
            if triage_results else 0.0
        )

        if total_latency > 2000:
            opts.append(
                OptimizationRecommendation(
                    category="latency",
                    title="Parallelize agent steps",
                    description="Agent trace total latency exceeds 2s. Consider async execution for independent agents.",
                    estimated_impact="high",
                    action_items=["Run triage and critic in parallel", "Use streaming for LLM calls"],
                )
            )

        if avg_conf < 0.7:
            opts.append(
                OptimizationRecommendation(
                    category="trust",
                    title="Improve confidence signals",
                    description="Average confidence is below 0.7. Add structured prompting and few-shot examples.",
                    estimated_impact="medium",
                    action_items=["Add few-shot examples to triage prompt", "Enforce JSON output schema"],
                )
            )

        if any(r.estimated_cost_usd > 0.02 for r in triage_results):
            opts.append(
                OptimizationRecommendation(
                    category="cost",
                    title="Reduce per-incident cost",
                    description="Some triage results estimated >$0.02. Use a smaller model for initial filtering.",
                    estimated_impact="medium",
                    action_items=["Use a routing model to filter low-priority incidents", "Enable response caching"],
                )
            )

        if not opts:
            opts.append(
                OptimizationRecommendation(
                    category="accuracy",
                    title="Add metadata enrichment",
                    description="Workflow is performing well. Enrich incidents with runbook links for faster resolution.",
                    estimated_impact="low",
                    action_items=["Attach runbook IDs to incidents", "Link related past incidents"],
                )
            )

        trace_builder.end_step(
            output_summary=f"{len(opts)} optimizations suggested",
            status="success",
        )
        return opts
