"""Collect AMD runtime telemetry and write a lightweight JSON snapshot."""

from __future__ import annotations

import argparse
import json
import platform
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Collect AMD runtime telemetry into a JSON file."
    )
    parser.add_argument(
        "--output",
        default="amd_runtime_signals.json",
        help="Output JSON path. Example: amd_runtime_signals.json",
    )
    args = parser.parse_args()

    payload = collect_runtime_signals()
    output_path = Path(args.output)
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote AMD runtime signals to {output_path}")


def collect_runtime_signals() -> dict:
    command = resolve_command()
    raw_output = ""
    rocm_version = None
    gpu_utilization_percent = None
    gpu_memory_percent = None
    temperature_c = None
    power_w = None

    if command is not None:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
        )
        raw_output = f"{result.stdout}\n{result.stderr}".strip()
        gpu_utilization_percent = first_float(r"GPU(?:\[\d+\])?.*?(\d+(?:\.\d+)?)%", raw_output)
        gpu_memory_percent = first_float(r"VRAM.*?(\d+(?:\.\d+)?)%", raw_output)
        temperature_c = first_float(r"Temp.*?(\d+(?:\.\d+)?)c", raw_output)
        power_w = first_float(r"Power.*?(\d+(?:\.\d+)?)W", raw_output)

    if shutil.which("rocminfo"):
        result = subprocess.run(
            ["rocminfo"],
            capture_output=True,
            text=True,
            check=False,
        )
        rocm_output = f"{result.stdout}\n{result.stderr}"
        version_match = re.search(r"ROCm\s+Version[:\s]+([^\s]+)", rocm_output, re.IGNORECASE)
        rocm_version = version_match.group(1) if version_match else None
        if not raw_output:
            raw_output = rocm_output.strip()

    return {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "node_name": platform.node(),
        "rocm_version": rocm_version,
        "gpu_utilization_percent": gpu_utilization_percent,
        "gpu_memory_percent": gpu_memory_percent,
        "temperature_c": temperature_c,
        "power_w": power_w,
        "raw": raw_output[:12000],
    }


def resolve_command() -> list[str] | None:
    if shutil.which("rocm-smi"):
        return ["rocm-smi", "--showuse", "--showmemuse", "--showtemp", "--showpower"]
    if shutil.which("amd-smi"):
        return ["amd-smi", "metric", "--gpu", "all"]
    return None


def first_float(pattern: str, text: str) -> float | None:
    match = re.search(pattern, text, re.IGNORECASE)
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


if __name__ == "__main__":
    main()
