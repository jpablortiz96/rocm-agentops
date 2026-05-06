"""Endpoint probing for AMD live signal intake."""

from __future__ import annotations

import time
from typing import Any, Dict, Optional

import requests


def probe_endpoint(
    *,
    base_url: str,
    model: str,
    api_key: str = "",
    timeout: int = 10,
) -> Dict[str, Any]:
    """Probe the configured OpenAI-compatible endpoint for basic health."""
    base = base_url.rstrip("/")
    if base.endswith("/v1"):
        api_root = base
    else:
        api_root = f"{base}/v1"
    models_url = f"{api_root}/models"
    chat_url = f"{api_root}/chat/completions"
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    models_status_code: Optional[int] = None
    models_available = False
    chat_available = False
    error_message: Optional[str] = None
    model_names: list[str] = []
    latency_ms: Optional[float] = None
    probe_response_preview: Optional[str] = None
    status_code: Optional[int] = None

    try:
        resp = requests.get(models_url, headers=headers, timeout=timeout)
        models_status_code = resp.status_code
        if resp.ok:
            models_available = True
            payload = resp.json()
            model_names = [item.get("id", "") for item in payload.get("data", [])[:10]]
    except requests.RequestException as exc:
        error_message = f"/models probe failed: {exc}"

    start = time.perf_counter()
    try:
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": "Return exactly: AMD live probe online"}],
            "temperature": 0.2,
            "max_tokens": 30,
        }
        resp = requests.post(chat_url, headers=headers, json=payload, timeout=timeout)
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        status_code = resp.status_code
        resp.raise_for_status()
        chat_available = True
        response_payload = resp.json()
        content = (
            response_payload.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )
        probe_response_preview = content[:160] or None
    except requests.RequestException as exc:
        if latency_ms is None:
            latency_ms = round((time.perf_counter() - start) * 1000, 2)
        status_code = status_code or getattr(getattr(exc, "response", None), "status_code", None)
        error_message = str(exc)

    endpoint_health = "healthy" if chat_available else "unavailable"

    return {
        "endpoint_available": chat_available,
        "endpoint_health": endpoint_health,
        "models_available": models_available,
        "chat_available": chat_available,
        "status_code": status_code,
        "models_status_code": models_status_code,
        "latency_ms": latency_ms,
        "model": model,
        "detected_models": model_names,
        "error": error_message,
        "probe_response_preview": probe_response_preview,
        "base_url": api_root,
    }
