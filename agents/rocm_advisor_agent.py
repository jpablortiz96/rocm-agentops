"""ROCm Advisor Agent: evaluates AMD/ROCm readiness."""

from typing import List

from core.llm_client import LLMClient, llm
from core.schemas import Incident, ROCmReadinessReport
from core.tracing import TraceBuilder


class ROCmAdvisorAgent:
    """Advises on ROCm/AMD compatibility and optimizations.

    Policy: structured output is always deterministic and factually curated.
    LLM narrative may be appended to notes, but never replaces structured fields.
    """

    SYSTEM_PROMPT = (
        "You are an AMD ROCm AI infrastructure advisor. Explain when AMD Developer Cloud, "
        "MI300X, ROCm, vLLM, batching, and open-source models such as Qwen, Llama, and Mistral matter."
    )

    def __init__(self, llm_client: LLMClient = llm):
        self.llm = llm_client
        self.name = "rocm_advisor"
        self.last_llm_meta = None

    def advise(
        self,
        model_name: str,
        trace_builder: TraceBuilder,
    ) -> ROCmReadinessReport:
        """Generate ROCm readiness advice."""
        trace_builder.start_step(
            "rocm_check", self.name, input_summary=f"model={model_name}"
        )

        # Deterministic defaults
        report = ROCmReadinessReport(
            model_compatible=True,
            gpu_recommendation="MI300X",
            kernel_optimizations=[
                "hipBLASLt",
                "MIOpen",
                "RCCL",
            ],
            quantization_suggestion="FP8 / INT8 via AMD-quant",
            notes=[
                "ROCm 6.1+ recommended for best Flash Attention support",
                "Ensure docker image uses rocm/pytorch base",
            ],
        )

        user_prompt = (
            f"You are an AMD ROCm specialist. Evaluate readiness for model '{model_name}'. "
            "Respond in 2 short bullets."
        )
        fallback = "ROCm readiness confirmed for this model."
        result = self.llm.chat(self.SYSTEM_PROMPT, user_prompt, fallback=fallback)
        self.last_llm_meta = result
        if result["content"] and result["content"] not in report.notes:
            report.notes.append(result["content"])

        trace_builder.end_step(
            output_summary=f"Compatible={report.model_compatible}, GPU={report.gpu_recommendation}",
            status="success",
        )
        return report

    def advise_batch(self, incidents: List[Incident]) -> ROCmReadinessReport:
        """Generate ROCm readiness advice based on incident batch.

        Returns a factually curated report. LLM output is appended to notes
        but never replaces structured fields like optimizations or limitations.
        """
        inference_incidents = [i for i in incidents if i.system == "inference"]
        if not inference_incidents:
            return ROCmReadinessReport(
                summary="No inference incidents detected. ROCm readiness is not a current blocker.",
                gpu_relevant_steps=[],
                rocm_optimizations=[],
                batching_opportunities=[],
                estimated_impact="low",
                limitations=[],
                model_compatible=True,
                gpu_recommendation="MI300X",
            )

        rocm_keywords = ["mi300x", "rocm", "triton", "gpu", "thermal", "throughput"]
        relevant = [
            i for i in inference_incidents
            if any(k in f"{i.title} {i.description}".lower() for k in rocm_keywords)
        ]

        # Curated, factually static report
        report = ROCmReadinessReport(
            summary=(
                f"{len(relevant)} inference incident(s) relate to AMD/ROCm stack. "
                "Recommend GPU profiling and kernel optimization."
            ),
            gpu_relevant_steps=[i.id for i in relevant],
            rocm_optimizations=[
                "Enable hipBLASLt for fused GEMM operations on MI300X",
                "Use MIOpen for optimized convolutions on AMD GPUs",
                "Switch to RCCL for multi-GPU communication",
                "Quantize to FP8/INT8 via AMD-quant for higher throughput",
            ],
            batching_opportunities=[
                "vLLM continuous batching on MI300X",
                "Dynamic split-fuse for decode-heavy workloads",
                "PagedAttention for long-context open-source models (Qwen, Llama, Mistral)",
            ],
            estimated_impact="high",
            limitations=[
                "ROCm 6.1+ required for best Flash Attention support",
                "Some Triton kernels may need manual tuning on MI300X",
                "Docker base image must use rocm/pytorch:latest",
                "Not all proprietary models are portable; open-source models are preferred",
            ],
            model_compatible=True,
            gpu_recommendation="MI300X",
            kernel_optimizations=["hipBLASLt", "MIOpen", "RCCL"],
            quantization_suggestion="FP8 / INT8 via AMD-quant",
            notes=[
                "AMD Developer Cloud provides cloud access to AMD GPUs for AI workloads",
                "ROCm is AMD's open software stack for GPU computing",
                "MI300X is relevant for high-throughput inference and large model serving",
                "vLLM provides OpenAI-compatible serving and batching for LLM inference",
                "Qwen models are from Alibaba; Llama models are from Meta; Mistral models are from Mistral AI",
                "Deterministic scoring does not need GPU",
                "LLM narrative generation, batching, and high-throughput serving are the GPU-relevant parts",
            ],
        )

        user_prompt = (
            f"An incident batch includes {len(inference_incidents)} inference incidents. "
            f"{len(relevant)} relate to AMD/ROCm keywords.\n\n"
            "Provide ROCm readiness advice mentioning MI300X, vLLM, AMD Developer Cloud, "
            "and open-source models (Qwen, Llama, Mistral). Respond in markdown bullet points."
        )

        result = self.llm.chat(self.SYSTEM_PROMPT, user_prompt)
        self.last_llm_meta = result

        # If real LLM was used, append its narrative to notes without replacing
        # any structured field.
        if result["used_llm"] and result["content"]:
            report.notes.append(f"LLM narrative: {result['content']}")

        return report
