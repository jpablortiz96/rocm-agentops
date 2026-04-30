"""ROCm Advisor Agent: evaluates AMD/ROCm readiness."""

from typing import List

from core.llm_client import LLMClient, llm
from core.schemas import Incident, ROCmReadinessReport
from core.tracing import TraceBuilder


class ROCmAdvisorAgent:
    """Advises on ROCm/AMD compatibility and optimizations."""

    def __init__(self, llm_client: LLMClient = llm):
        self.llm = llm_client
        self.name = "rocm_advisor"

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

        if not self.llm.mock:
            prompt = (
                f"You are an AMD ROCm specialist. Evaluate readiness for model '{model_name}'. "
                f"Respond in 2 short bullets."
            )
            resp = self.llm.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=256,
            )
            text = self.llm.extract_content(resp)
            report.notes.append(text)

        trace_builder.end_step(
            output_summary=f"Compatible={report.model_compatible}, GPU={report.gpu_recommendation}",
            status="success",
        )
        return report

    def advise_batch(self, incidents: List[Incident]) -> ROCmReadinessReport:
        """Generate ROCm readiness advice based on incident batch."""
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

        if self.llm.mock:
            summary = (
                f"{len(relevant)} inference incident(s) relate to AMD/ROCm stack. "
                "Recommend immediate GPU profiling and kernel optimization."
            )
            return ROCmReadinessReport(
                summary=summary,
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
                    "Not all proprietary models are portable; open-source models (Qwen, Llama, Mistral) are preferred",
                ],
                model_compatible=True,
                gpu_recommendation="MI300X",
                kernel_optimizations=["hipBLASLt", "MIOpen", "RCCL"],
                quantization_suggestion="FP8 / INT8 via AMD-quant",
                notes=[
                    "AMD Developer Cloud provides MI300X instances for testing and benchmarking",
                    "ROCm 6.1+ recommended for best Flash Attention support",
                    "Ensure docker image uses rocm/pytorch base",
                    "vLLM on ROCm supports Qwen, Llama, Mistral families with competitive throughput",
                ],
            )

        prompt = (
            "You are an AMD ROCm specialist. "
            "An incident batch includes inference workloads. "
            "Provide ROCm readiness advice mentioning MI300X, vLLM, AMD Developer Cloud, "
            "and open-source models (Qwen, Llama, Mistral). "
            "Respond in markdown bullet points."
        )
        resp = self.llm.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=512,
        )
        text = self.llm.extract_content(resp)
        return ROCmReadinessReport(
            summary="LLM-generated ROCm readiness advice.",
            gpu_relevant_steps=[i.id for i in relevant],
            rocm_optimizations=[text],
            batching_opportunities=["vLLM continuous batching"],
            estimated_impact="medium",
            limitations=["Review LLM output for accuracy"],
            model_compatible=True,
            gpu_recommendation="MI300X",
            kernel_optimizations=["hipBLASLt", "MIOpen", "RCCL"],
            quantization_suggestion="FP8 / INT8 via AMD-quant",
            notes=[text],
        )
