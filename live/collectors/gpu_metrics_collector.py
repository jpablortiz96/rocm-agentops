"""Optional GPU telemetry collector for AMD live signal intake."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict


def collect_gpu_metrics(
    timeout: int = 10,
    *,
    runtime_signals_path: str = "data/amd_runtime_signals.json",
) -> Dict[str, Any]:
    """Collect lightweight ROCm GPU metrics from file or local tooling."""
    file_metrics = _load_runtime_signals_file(runtime_signals_path)
    if file_metrics is not None:
        return file_metrics

    command = _resolve_gpu_command()
    if command is None:
        return {
            "available": False,
            "reason": "GPU telemetry unavailable",
            "source": "none",
        }

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except Exception as exc:  # noqa: BLE001
        return {"available": False, "reason": str(exc), "source": "command"}

    output = f"{result.stdout}\n{result.stderr}".strip()
    if not output:
        return {
            "available": False,
            "reason": "GPU telemetry command returned no output",
            "source": "command",
        }

    return {
        "available": True,
        "source": "command",
        "command": " ".join(command),
        "utilization_pct": _first_float(r"GPU(?:\[\d+\])?.*?(\d+(?:\.\d+)?)%", output),
        "memory_usage_pct": _first_float(r"VRAM.*?(\d+(?:\.\d+)?)%", output),
        "temperature_c": _first_float(r"Temp.*?(\d+(?:\.\d+)?)c", output),
        "power_w": _first_float(r"Power.*?(\d+(?:\.\d+)?)W", output),
        "raw_output": output[:4000],
    }


def _load_runtime_signals_file(path: str) -> Dict[str, Any] | None:
    signals_path = Path(path)
    if not signals_path.exists():
        return None

    try:
        payload = json.loads(signals_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {
            "available": False,
            "reason": f"Unable to parse {signals_path}",
            "source": "file",
        }

    return {
        "available": True,
        "source": "file",
        "path": str(signals_path),
        "captured_at": payload.get("captured_at"),
        "node_name": payload.get("node_name"),
        "rocm_version": payload.get("rocm_version"),
        "utilization_pct": payload.get("gpu_utilization_percent"),
        "memory_usage_pct": payload.get("gpu_memory_percent"),
        "temperature_c": payload.get("temperature_c"),
        "power_w": payload.get("power_w"),
        "duration_seconds": payload.get("duration_seconds"),
        "raw_output": payload.get("raw"),
    }


def _resolve_gpu_command() -> list[str] | None:
    if shutil.which("rocm-smi"):
        return ["rocm-smi", "--showuse", "--showmemuse", "--showtemp", "--showpower"]
    if shutil.which("amd-smi"):
        return ["amd-smi", "metric", "--gpu", "all"]
    return None


def _first_float(pattern: str, text: str) -> float | None:
    match = re.search(pattern, text, re.IGNORECASE)
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None
