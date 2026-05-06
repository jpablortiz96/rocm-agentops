"""AMD benchmark utilities: load, save, analyze, and format results."""

import json
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from core.benchmark_schemas import AmdBenchmarkSummary, AmdEvidencePack


def estimate_tokens(text: str) -> int:
    """Rough token estimate: characters / 4."""
    return max(1, len(text) // 4)


def percentile(values: list[float], p: float) -> float:
    """Return the p-th percentile of a list of floats using linear interpolation."""
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    k = (n - 1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, n - 1)
    if f == c:
        return sorted_vals[f]
    return sorted_vals[f] * (c - k) + sorted_vals[c] * (k - f)


def load_benchmark_results(path: str) -> Optional[AmdBenchmarkSummary]:
    """Load benchmark JSON from disk. Returns None if missing or invalid."""
    p = Path(path)
    if not p.exists():
        return None
    try:
        with open(p, "r", encoding="utf-8") as f:
            raw = json.load(f)
        return AmdBenchmarkSummary.model_validate(raw)
    except Exception:
        return None


def load_preferred_benchmark_results(
    primary_path: str = "data/amd_benchmark_results.json",
    example_path: str = "data/amd_benchmark_results.example.json",
) -> Optional[AmdBenchmarkSummary]:
    """Load the submitted benchmark artifact, or fall back to the bundled example."""
    primary = load_benchmark_results(primary_path)
    if primary is not None:
        primary.artifact_origin = "submitted"
        return primary

    example = load_benchmark_results(example_path)
    if example is not None:
        example.artifact_origin = "example"
        note = "Loaded from the bundled example benchmark artifact."
        if note not in example.notes:
            example.notes.append(note)
        return example

    return None


def save_benchmark_results(summary: AmdBenchmarkSummary, path: str) -> None:
    """Serialize benchmark results to JSON."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(summary.model_dump(mode="json"), f, indent=2)


def build_evidence_pack(summary: AmdBenchmarkSummary | dict[str, Any]) -> AmdEvidencePack:
    """Generate claims, limitations, and next steps from a benchmark summary."""
    summary_model = _coerce_benchmark_summary(summary)
    verified = summary_model.successful_requests > 0

    if verified:
        claims = [
            "This workflow can connect to an OpenAI-compatible model endpoint.",
            "Benchmark results were captured from the configured endpoint.",
            "Deterministic scoring remains local and does not consume GPU.",
            "LLM narrative steps can be batched and accelerated through GPU-backed serving.",
        ]
        if summary_model.avg_latency_ms < 500:
            claims.append(
                "Average latency is under 500ms, suitable for real-time agent assistance."
            )
        if (
            summary_model.successful_requests == summary_model.total_requests
            and summary_model.total_requests > 0
        ):
            claims.append("All benchmark requests succeeded with zero failures.")
    else:
        claims = []

    limitations = [
        "Benchmarks reflect point-in-time endpoint performance.",
        "Token estimates are heuristic (len(text)/4) and not exact.",
        "Results may vary with different model sizes and quantization settings.",
    ]
    if not verified:
        limitations.append(
            "Endpoint was reachable but chat completions failed. No valid throughput can be claimed."
        )
        limitations.append(
            "Fix endpoint/model path before using as AMD evidence."
        )

    if verified:
        next_steps = [
            "Run benchmarks at multiple concurrency levels to find throughput saturation.",
            "Compare results against baseline CPU-only inference.",
            "Profile with rocProf on MI300X to identify kernel-level optimizations.",
        ]
    else:
        next_steps = [
            "Verify the endpoint URL and model identifier are correct.",
            "Check that the endpoint is running and accessible from this machine.",
            "Review error messages in the request results table above.",
        ]

    return AmdEvidencePack(
        summary=summary_model.model_dump(mode="json"),
        amd_claims=claims,
        limitations=limitations,
        recommended_next_steps=next_steps,
    )


def _coerce_benchmark_summary(
    summary: AmdBenchmarkSummary | dict[str, Any],
) -> AmdBenchmarkSummary:
    """Normalize benchmark inputs across Streamlit reruns and module reloads."""
    if isinstance(summary, AmdBenchmarkSummary):
        return summary
    if hasattr(summary, "model_dump"):
        return AmdBenchmarkSummary.model_validate(summary.model_dump(mode="json"))
    return AmdBenchmarkSummary.model_validate(summary)


def generate_benchmark_markdown(evidence_pack: AmdEvidencePack) -> str:
    """Render an evidence pack as a markdown report."""
    s = evidence_pack.summary
    verified = s.successful_requests > 0
    lines = [
        "# AMD Live Benchmark Report",
        "",
        f"**Run ID:** {s.run_id}",
        f"**Timestamp:** {s.timestamp}",
        f"**Endpoint:** {s.endpoint_base_url}",
        f"**Model:** {s.model}",
        f"**Mock Mode:** {'ON' if s.mock_mode else 'OFF'}",
        f"**Verified:** {'Yes' if verified else 'No'}",
        "",
        "## Summary",
        f"- **Total Requests:** {s.total_requests}",
        f"- **Successful:** {s.successful_requests}",
        f"- **Failed:** {s.failed_requests}",
        f"- **Benchmark Duration:** {s.benchmark_duration_seconds:.2f}s",
        "",
        "## Latency Metrics",
    ]
    if verified:
        lines.append(f"- **Average:** {s.avg_latency_ms:.2f} ms")
        lines.append(f"- **p50:** {s.p50_latency_ms:.2f} ms")
        lines.append(f"- **p95:** {s.p95_latency_ms:.2f} ms")
    else:
        lines.append("- **Average:** N/A (no successful requests)")
        lines.append("- **p50:** N/A (no successful requests)")
        lines.append("- **p95:** N/A (no successful requests)")
    lines.append("")
    lines.append("## Throughput")
    if verified:
        lines.append(f"- **Estimated Total Tokens:** {s.estimated_total_tokens}")
        lines.append(f"- **Estimated Tokens/sec:** {s.estimated_tokens_per_second:.2f}")
    else:
        lines.append("- **Estimated Total Tokens:** N/A")
        lines.append("- **Estimated Tokens/sec:** N/A")
    lines.append(f"- **Concurrency Levels Tested:** {s.concurrency_levels}")
    lines.append("")
    if verified:
        lines.append("## AMD Evidence Claims")
    else:
        lines.append("## AMD Evidence Claims")
        lines.append("*No claims can be made because all benchmark requests failed.*")
        lines.append("")
    for claim in evidence_pack.amd_claims:
        lines.append(f"- {claim}")
    lines.append("")
    lines.append("## Limitations")
    for lim in evidence_pack.limitations:
        lines.append(f"- {lim}")
    lines.append("")
    lines.append("## Recommended Next Steps")
    for step in evidence_pack.recommended_next_steps:
        lines.append(f"- {step}")
    lines.append("")
    lines.append("## Detailed Request Results")
    lines.append(
        "| Request ID | Prompt Type | Success | Latency (ms) | Input Tok | Output Tok | Error |"
    )
    lines.append(
        "|------------|-------------|---------|-------------|-----------|------------|-------|"
    )
    for r in s.request_results:
        err = r.error or "—"
        lines.append(
            f"| {r.request_id} | {r.prompt_type} | {'✓' if r.success else '✗'} | "
            f"{r.latency_ms:.2f} | {r.estimated_input_tokens} | {r.estimated_output_tokens} | {err} |"
        )
    lines.append("")
    return "\n".join(lines)
