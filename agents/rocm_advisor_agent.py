"""ROCm Advisor Agent: evaluates AMD/ROCm readiness."""

from core.llm_client import LLMClient, llm
from core.schemas import ROCmReadinessReport
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
