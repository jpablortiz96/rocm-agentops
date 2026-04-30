"""Optimizer Agent: suggests cost, latency, and accuracy improvements."""

from typing import List

from core.llm_client import LLMClient, llm
from core.schemas import AgentTrace, OptimizationRecommendation, TriageDecision, TriageResult
from core.tracing import TraceBuilder


class OptimizerAgent:
    """Generates optimization recommendations for the agentic workflow."""

    SYSTEM_PROMPT = (
        "You are an AI cost and latency optimization expert for agentic workflows. "
        "Recommend deterministic logic, smaller models, caching, batching, and AMD/ROCm/vLLM optimizations."
    )

    def __init__(self, llm_client: LLMClient = llm):
        self.llm = llm_client
        self.name = "optimizer"
        self.last_llm_meta = None

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

    def optimize_batch(
        self,
        triage_decisions: List[TriageDecision],
    ) -> List[OptimizationRecommendation]:
        """Produce optimization recommendations for AgentOps demo."""
        # Deterministic fallback recommendations
        fallback_opts = [
            OptimizationRecommendation(
                category="cost",
                title="Use Deterministic Scoring for Priority Routing",
                description="Priority, confidence, and trust scores should be computed deterministically without LLM calls. This eliminates latency and cost for the ranking step.",
                recommendation="Route all incidents through deterministic scoring first. Only use LLMs for explanation, critique, and report generation.",
                expected_benefit="Eliminate LLM cost and latency for the ranking step (60-80% of workflow time).",
                complexity="low",
                estimated_impact="high",
                action_items=[
                    "Keep deterministic scoring as the backbone",
                    "Use LLM only for explanation and critique layers",
                ],
            ),
            OptimizationRecommendation(
                category="cost",
                title="Use Smaller Models for Summaries",
                description="Critic reviews and optimizer suggestions can run on smaller models with lower token counts.",
                recommendation="Switch summary and critique generation to a 7B-parameter model or distilled variant.",
                expected_benefit="Reduce token cost by 40-60% for non-critical steps.",
                complexity="low",
                estimated_impact="medium",
                action_items=[
                    "Use Qwen-7B or Llama-3.1-8B for summaries",
                    "Route only final report assembly to the largest model",
                ],
            ),
            OptimizationRecommendation(
                category="latency",
                title="Batch Inference for Many Incidents",
                description="When incident volume spikes, batching LLM calls reduces overhead.",
                recommendation="Group similar incidents into batches and run a single LLM prompt per batch.",
                expected_benefit="Reduce per-incident latency by 30-50% during spikes.",
                complexity="medium",
                estimated_impact="medium",
                action_items=[
                    "Implement batch prompt templates",
                    "Use vLLM continuous batching on AMD MI300X",
                ],
            ),
            OptimizationRecommendation(
                category="latency",
                title="Cache Repeated Reports",
                description="Final reports for identical incident signatures are often regenerated.",
                recommendation="Cache markdown reports keyed by incident hash.",
                expected_benefit="Eliminate redundant LLM calls for duplicate signatures.",
                complexity="low",
                estimated_impact="medium",
                action_items=[
                    "Add Redis cache for report markdown",
                    "Invalidate cache when evidence changes",
                ],
            ),
            OptimizationRecommendation(
                category="latency",
                title="Deploy on AMD MI300X with ROCm + vLLM",
                description="High-throughput open-source inference (Qwen, Llama, Mistral) runs efficiently on AMD MI300X with ROCm.",
                recommendation="Serve models via vLLM on MI300X with hipBLASLt and FP8 quantization for maximum throughput.",
                expected_benefit="2-4x higher throughput per dollar compared to standard cloud GPU instances.",
                complexity="medium",
                estimated_impact="high",
                action_items=[
                    "Provision AMD Developer Cloud MI300X instances",
                    "Enable vLLM with continuous batching",
                    "Quantize to FP8/INT8 via AMD-quant",
                    "Profile with rocProf and optimize Triton kernels",
                ],
            ),
        ]

        user_prompt = (
            f"Analyze these {len(triage_decisions)} triage decisions and suggest 3-5 concrete "
            "improvements to reduce cost, latency, or improve accuracy.\n\n"
            + "\n".join(
                f"- {d.incident_id}: priority={d.priority_score}, confidence={d.confidence_score}"
                for d in triage_decisions[:10]
            )
            + "\n\nMention deterministic scoring, smaller models, caching, batching, and "
            "AMD/ROCm/MI300X/vLLM where relevant. Respond in markdown bullet points."
        )

        result = self.llm.chat(self.SYSTEM_PROMPT, user_prompt)
        self.last_llm_meta = result

        # If real LLM was used, wrap its output in a single recommendation
        if result["used_llm"]:
            return [
                OptimizationRecommendation(
                    category="trust",
                    title="LLM-Generated Optimizations",
                    description=result["content"],
                    recommendation="Review the generated suggestions and prioritize by impact.",
                    expected_benefit="Varies by suggestion",
                    complexity="medium",
                    estimated_impact="medium",
                )
            ]

        return fallback_opts
