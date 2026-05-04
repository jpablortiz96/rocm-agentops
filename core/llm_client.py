"""LLM client with mock mode and OpenAI-compatible support."""

import time
import uuid
from typing import Any, Dict, List, Optional

import requests

from core.config import config


class LLMClient:
    """Lightweight OpenAI-compatible LLM client with safe fallback."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        mock: Optional[bool] = None,
    ):
        self.api_key = api_key or config.LLM_API_KEY
        # Normalize base_url: strip trailing slashes so /chat/completions is clean.
        self.base_url = (base_url or config.LLM_BASE_URL).rstrip("/")
        self.model = model or config.LLM_MODEL
        self.mock = mock if mock is not None else config.is_mock()
        self.timeout = config.LLM_TIMEOUT

    def chat(
        self,
        system_prompt: str,
        user_prompt: str,
        fallback: str = "",
    ) -> Dict[str, Any]:
        """Call chat.completions or return mock/fallback response.

        Returns a dict with:
        - content: str
        - used_llm: bool
        - used_mock: bool
        - error: str | None
        - model: str
        - estimated_input_tokens: int
        - estimated_output_tokens: int
        - estimated_cost_usd: float
        """
        if self.mock:
            content = fallback or self._mock_content(user_prompt)
            return {
                "content": content,
                "used_llm": False,
                "used_mock": True,
                "error": None,
                "model": self.model,
                "estimated_input_tokens": (len(system_prompt) + len(user_prompt)) // 4,
                "estimated_output_tokens": len(content) // 4,
                "estimated_cost_usd": 0.0,
            }

        # Build URL: if base_url ends with /v1, append /chat/completions;
        # otherwise append /v1/chat/completions to match standard OpenAI layout.
        base = self.base_url
        if base.endswith("/v1"):
            url = f"{base}/chat/completions"
        else:
            url = f"{base}/v1/chat/completions"

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
            "max_tokens": 700,
        }

        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
            content = self._extract_content(data) or fallback or self._mock_content(user_prompt)
            estimated_input_tokens = (len(system_prompt) + len(user_prompt)) // 4
            estimated_output_tokens = len(content) // 4
            # Mock cost estimate: $2 per 1M tokens (clearly marked as estimated).
            estimated_cost_usd = (estimated_input_tokens + estimated_output_tokens) * 0.000002
            return {
                "content": content,
                "used_llm": True,
                "used_mock": False,
                "error": None,
                "model": self.model,
                "estimated_input_tokens": estimated_input_tokens,
                "estimated_output_tokens": estimated_output_tokens,
                "estimated_cost_usd": estimated_cost_usd,
            }
        except requests.RequestException as exc:
            content = fallback or self._mock_content(user_prompt)
            return {
                "content": content,
                "used_llm": False,
                "used_mock": True,
                "error": str(exc),
                "model": self.model,
                "estimated_input_tokens": 0,
                "estimated_output_tokens": 0,
                "estimated_cost_usd": 0.0,
            }

    def _mock_content(self, user_prompt: str) -> str:
        """Simple rule-based mock content derived from prompt keywords."""
        lowered = user_prompt.lower()
        if "plan" in lowered or "execution" in lowered:
            return (
                "1. Validate incident schema.\n"
                "2. Compute deterministic priority scores.\n"
                "3. Detect risk flags.\n"
                "4. Compare against baseline.\n"
                "5. Generate critic review.\n"
                "6. Produce ROCm readiness report.\n"
                "7. Assemble final audit report."
            )
        if "critic" in lowered or "review" in lowered:
            return "Review complete. Confidence is acceptable. Add more metadata to improve traceability."
        if "optimize" in lowered or "improvement" in lowered:
            return (
                "- Use deterministic scoring for priority routing.\n"
                "- Use smaller models (7B) for summaries.\n"
                "- Batch inference for many incidents.\n"
                "- Cache repeated reports.\n"
                "- Deploy on AMD MI300X with ROCm + vLLM."
            )
        if "rocm" in lowered or "amd" in lowered or "gpu" in lowered:
            return (
                "- Enable hipBLASLt for fused GEMM on MI300X.\n"
                "- Use MIOpen for optimized convolutions.\n"
                "- Switch to RCCL for multi-GPU communication.\n"
                "- Quantize to FP8/INT8 via AMD-quant.\n"
                "- Use vLLM continuous batching on MI300X."
            )
        return "Acknowledged. Proceed with standard operating procedures."

    def _extract_content(self, response: Dict[str, Any]) -> Optional[str]:
        """Safely extract assistant text from API response."""
        try:
            return response["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            return None

    # ------------------------------------------------------------------
    # Legacy interface (kept for backward compatibility)
    # ------------------------------------------------------------------

    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 512,
    ) -> Dict[str, Any]:
        """Deprecated: use chat() instead."""
        system_msg = next((m["content"] for m in messages if m.get("role") == "system"), "")
        user_msg = next((m["content"] for m in reversed(messages) if m.get("role") == "user"), "")
        result = self.chat(system_msg, user_msg)
        # Re-package into old response format
        return {
            "id": f"chatcmpl-{uuid.uuid4().hex[:8]}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": result["model"],
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": result["content"]},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": result["estimated_input_tokens"],
                "completion_tokens": result["estimated_output_tokens"],
                "total_tokens": result["estimated_input_tokens"] + result["estimated_output_tokens"],
            },
        }

    def extract_content(self, response: Dict[str, Any]) -> str:
        """Deprecated: use chat()['content'] instead."""
        return self._extract_content(response) or ""


# Singleton convenience
llm = LLMClient()
