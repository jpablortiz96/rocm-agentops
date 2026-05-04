"""Optimizer Agent: suggests cost, latency, and accuracy improvements."""

from typing import List

from core.llm_client import LLMClient, llm
from core.schemas import AgentTrace, OptimizationRecommendation, TriageDecision, TriageResult
from core.tracing import TraceBuilder


class OptimizerAgent:
    """Generates optimization recommendations for the agentic workflow.

    Policy: always return 5 structured, deterministic recommendations.
    LLM may add a concise rationale field, but never replaces the curated list.
    """

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
        """Produce 5 structured optimization recommendations for AgentOps demo.

        The 5 recommendations are deterministic and curated. If a real LLM is used,
        its output is appended as a rationale on the first recommendation without
        replacing the structured list.
        """
        # Curated, deterministic recommendations
        recommendations = [
            OptimizationRecommendation(
                category="reliability/cost",
                title="Keep Priority Scoring Deterministic",
                description="Priority, confidence, and trust scores are computed mathematically without LLM calls. This preserves auditability and eliminates ranking latency.",
                recommendation="Route all incidents through deterministic scoring first. Only use LLMs for explanation, critique, and report generation.",
                expected_benefit="Avoid unnecessary LLM calls for ranking and preserve auditability.",
                complexity="low",
                estimated_impact="high",
                action_items=[
                    "Keep deterministic scoring as the backbone",
                    "Use LLM only for explanation and critique layers",
                ],
            ),
            OptimizationRecommendation(
                category="latency/throughput",
                title="Batch LLM Narrative Steps on AMD/vLLM",
                description="Planner, critic, optimizer, ROCm advisor, and reporter prompts can be batched when incident volume increases.",
                recommendation="Group similar incidents into batches and run a single LLM prompt per batch on AMD/vLLM.",
                expected_benefit="Planner, critic, optimizer, ROCm advisor, and reporter prompts can be batched when incident volume increases.",
                complexity="medium",
                estimated_impact="high",
                action_items=[
                    "Implement batch prompt templates",
                    "Use vLLM continuous batching on AMD MI300X",
                ],
            ),
            OptimizationRecommendation(
                category="cost/quality",
                title="Route by Risk Tier",
                description="Low-risk incidents do not need LLM critique. High-risk incidents trigger LLM review and human escalation.",
                recommendation="Use deterministic trust score and risk flags to route incidents. Only escalate high-risk or ambiguous cases to LLM critique.",
                expected_benefit="Low-risk incidents use deterministic templates; high-risk incidents trigger LLM critique and human review.",
                complexity="low",
                estimated_impact="high",
                action_items=[
                    "Set trust-score threshold for LLM critique routing",
                    "Auto-batch low-risk incidents into template responses",
                ],
            ),
            OptimizationRecommendation(
                category="cost/latency",
                title="Cache Repeated Incident Reports",
                description="Final reports for identical incident signatures are often regenerated.",
                recommendation="Cache markdown reports keyed by incident hash and invalidate when evidence changes.",
                expected_benefit="Avoid regenerating similar summaries for recurring incident signatures.",
                complexity="low",
                estimated_impact="medium",
                action_items=[
                    "Add Redis cache for report markdown",
                    "Invalidate cache when evidence changes",
                ],
            ),
            OptimizationRecommendation(
                category="infrastructure",
                title="Use AMD Developer Cloud for Open-Source Model Serving",
                description="ROCm and vLLM provide an open, controllable stack for serving Qwen, Llama, and Mistral-class models.",
                recommendation="Serve Qwen/Llama/Mistral-class models through ROCm/vLLM for controllable, open-source agent infrastructure.",
                expected_benefit="Serve Qwen/Llama/Mistral-class models through ROCm/vLLM for controllable, open-source agent infrastructure.",
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

        # If real LLM was used, append its narrative as a rationale on the first
        # recommendation without replacing the curated list.
        if result["used_llm"] and result["content"]:
            recommendations[0].rationale = result["content"]

        return recommendations
