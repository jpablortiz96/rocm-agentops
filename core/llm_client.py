"""LLM client with mock mode and OpenAI-compatible support."""

import time
import uuid
from typing import Any, Dict, List, Optional

import requests

from core.config import config


class LLMClient:
    """Lightweight OpenAI-compatible LLM client."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        mock: Optional[bool] = None,
    ):
        self.api_key = api_key or config.LLM_API_KEY
        self.base_url = (base_url or config.LLM_BASE_URL).rstrip("/")
        self.model = model or config.LLM_MODEL
        self.mock = mock if mock is not None else config.is_mock()
        self.timeout = config.LLM_TIMEOUT

    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 512,
    ) -> Dict[str, Any]:
        """Call chat.completions or return mock response."""
        if self.mock:
            return self._mock_response(messages)

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=self.timeout)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            # Graceful degradation to mock on failure
            return self._mock_response(messages, error_note=str(exc))

    def _mock_response(
        self, messages: List[Dict[str, str]], error_note: Optional[str] = None
    ) -> Dict[str, Any]:
        """Deterministic mock response for demos and fallback."""
        user_msg = next((m["content"] for m in reversed(messages) if m.get("role") == "user"), "")
        content = self._generate_mock_content(user_msg)
        if error_note:
            content += f"\n\n(Mock fallback due to: {error_note})"

        return {
            "id": f"mock-{uuid.uuid4().hex[:8]}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": self.model,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": content},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        }

    def _generate_mock_content(self, user_msg: str) -> str:
        """Simple rule-based mock content derived from prompt."""
        lowered = user_msg.lower()
        if "triage" in lowered or "priority" in lowered:
            return "Priority: HIGH. Reasoning: Service degradation detected. Recommend immediate rollback and investigation."
        if "optimize" in lowered or "improve" in lowered:
            return "Optimization: Use FP8 quantization and enable Flash Attention for ROCm."
        if "rocm" in lowered or "amd" in lowered:
            return "ROCm Readiness: Compatible. Recommended GPU: MI300X. Enable hipBLASLt for matmul acceleration."
        if "critic" in lowered or "review" in lowered:
            return "Review: Confidence is acceptable. Add more metadata to improve traceability."
        return "Acknowledged. Proceed with standard operating procedures."

    def extract_content(self, response: Dict[str, Any]) -> str:
        """Safely extract assistant text from API response."""
        try:
            return response["choices"][0]["message"]["content"]
        except (KeyError, IndexError):
            return ""


# Singleton convenience
llm = LLMClient()
