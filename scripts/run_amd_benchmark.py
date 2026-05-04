#!/usr/bin/env python
"""Run AMD benchmark against an OpenAI-compatible endpoint."""

import argparse
import concurrent.futures
import statistics
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import requests

# Ensure imports resolve when running from scripts/
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from agents.critic_agent import CriticAgent
from agents.optimizer_agent import OptimizerAgent
from agents.planner_agent import PlannerAgent
from agents.reporter_agent import ReporterAgent
from agents.rocm_advisor_agent import ROCmAdvisorAgent
from core.benchmark_schemas import BenchmarkRequestResult, AmdBenchmarkSummary
from core.benchmarking import (
    build_evidence_pack,
    estimate_tokens,
    generate_benchmark_markdown,
    percentile,
    save_benchmark_results,
)


PROMPTS = {
    "planner": {
        "system": PlannerAgent.SYSTEM_PROMPT,
        "user": (
            "Create a concise 7-step execution plan for triaging 5 incidents: "
            "payments outage, suspicious IAM activity, LLM hallucination risk, "
            "MI300X inference degradation, database connection exhaustion."
        ),
    },
    "critic": {
        "system": CriticAgent.SYSTEM_PROMPT,
        "user": (
            "Review these 5 triage decisions:\n"
            "- INC-001: priority=92, trust=78, human_review=False, flags=[]\n"
            "- INC-004: priority=88, trust=42, human_review=True, flags=['MISSING_EVIDENCE','SECURITY_WITHOUT_EVIDENCE']\n"
            "- INC-007: priority=85, trust=65, human_review=True, flags=['HALLUCINATION_RISK']\n"
            "- INC-006: priority=83, trust=70, human_review=True, flags=['AMD_GPU_INFERENCE_DEGRADATION']\n"
            "- INC-011: priority=75, trust=60, human_review=False, flags=[]\n\n"
            "Highlight low-trust high-priority cases, missing evidence, hallucination risk, "
            "or security gaps. Use markdown bullets. Be concise."
        ),
    },
    "optimizer": {
        "system": OptimizerAgent.SYSTEM_PROMPT,
        "user": (
            "Analyze these 5 triage decisions and suggest 3-5 concrete improvements:\n"
            "- INC-001: priority=92, confidence=0.88\n"
            "- INC-004: priority=88, confidence=0.55\n"
            "- INC-007: priority=85, confidence=0.72\n"
            "- INC-006: priority=83, confidence=0.76\n"
            "- INC-011: priority=75, confidence=0.68\n\n"
            "Mention deterministic scoring, smaller models, caching, batching, and "
            "AMD/ROCm/MI300X/vLLM where relevant. Respond in markdown bullet points."
        ),
    },
    "rocm_advisor": {
        "system": ROCmAdvisorAgent.SYSTEM_PROMPT,
        "user": (
            "An incident batch includes 2 inference incidents related to MI300X and ROCm. "
            "Provide ROCm readiness advice mentioning MI300X, vLLM, AMD Developer Cloud, "
            "and open-source models (Qwen, Llama, Mistral). Respond in markdown bullet points."
        ),
    },
    "reporter": {
        "system": ReporterAgent.SYSTEM_PROMPT,
        "user": (
            "Write a 2-sentence executive summary for an incident triage report covering "
            "5 incidents, 5 triage decisions, 4 optimizations, and 8 trace events. "
            "Be concise and honest."
        ),
    },
}


def send_request(
    base_url: str,
    model: str,
    api_key: str,
    prompt_type: str,
    system_prompt: str,
    user_prompt: str,
):
    """Send a single chat completion request and return timing + token estimates."""
    url = f"{base_url.rstrip('/')}/chat/completions"
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.2,
        "max_tokens": 500,
    }
    t0 = time.perf_counter()
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        latency_ms = (time.perf_counter() - t0) * 1000
        input_tok = estimate_tokens(system_prompt + user_prompt)
        output_tok = estimate_tokens(content)
        return {
            "success": True,
            "latency_ms": latency_ms,
            "estimated_input_tokens": input_tok,
            "estimated_output_tokens": output_tok,
            "error": None,
        }
    except Exception as exc:
        latency_ms = (time.perf_counter() - t0) * 1000
        return {
            "success": False,
            "latency_ms": latency_ms,
            "estimated_input_tokens": estimate_tokens(system_prompt + user_prompt),
            "estimated_output_tokens": 0,
            "error": str(exc),
        }


def run_benchmark(base_url: str, model: str, api_key: str, concurrency_levels, repeat: int):
    """Execute the full benchmark suite and return an AmdBenchmarkSummary."""
    run_id = f"amd-bench-{uuid.uuid4().hex[:12]}"
    start_time = time.perf_counter()
    all_results = []

    for concurrency in concurrency_levels:
        print(f"Running concurrency level: {concurrency}")
        tasks = []
        for _ in range(repeat):
            for prompt_type, prompts in PROMPTS.items():
                tasks.append((prompt_type, prompts["system"], prompts["user"]))

        with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = {
                executor.submit(
                    send_request, base_url, model, api_key, pt, sp, up
                ): (pt, sp, up)
                for pt, sp, up in tasks
            }
            for future in concurrent.futures.as_completed(futures):
                pt, sp, up = futures[future]
                try:
                    res = future.result()
                except Exception as exc:
                    res = {
                        "success": False,
                        "latency_ms": 0.0,
                        "estimated_input_tokens": estimate_tokens(sp + up),
                        "estimated_output_tokens": 0,
                        "error": str(exc),
                    }
                all_results.append(
                    BenchmarkRequestResult(
                        request_id=f"{run_id}-{pt}-{len(all_results)}",
                        prompt_type=pt,
                        success=res["success"],
                        latency_ms=round(res["latency_ms"], 2),
                        estimated_input_tokens=res["estimated_input_tokens"],
                        estimated_output_tokens=res["estimated_output_tokens"],
                        estimated_total_tokens=res["estimated_input_tokens"]
                        + res["estimated_output_tokens"],
                        error=res["error"],
                    )
                )

    duration = time.perf_counter() - start_time
    latencies = [r.latency_ms for r in all_results if r.success]

    total_tok = sum(r.estimated_total_tokens for r in all_results)
    successful = sum(1 for r in all_results if r.success)
    failed = len(all_results) - successful

    notes = [
        "Benchmark run against OpenAI-compatible endpoint.",
        f"Tested concurrency levels: {list(concurrency_levels)}.",
    ]
    if successful == 0:
        notes.append("No successful requests; metrics are not valid.")

    summary = AmdBenchmarkSummary(
        run_id=run_id,
        timestamp=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        endpoint_base_url=base_url,
        model=model,
        mock_mode=False,
        total_requests=len(all_results),
        successful_requests=successful,
        failed_requests=failed,
        concurrency_levels=list(concurrency_levels),
        avg_latency_ms=round(statistics.mean(latencies), 2) if latencies else 0.0,
        p50_latency_ms=round(percentile(latencies, 50), 2) if latencies else 0.0,
        p95_latency_ms=round(percentile(latencies, 95), 2) if latencies else 0.0,
        estimated_total_tokens=total_tok,
        estimated_tokens_per_second=round(total_tok / duration, 2) if duration > 0 else 0.0,
        benchmark_duration_seconds=round(duration, 2),
        notes=notes,
        request_results=all_results,
        benchmark_verified=successful > 0,
    )
    return summary


def main():
    parser = argparse.ArgumentParser(
        description="Run AMD benchmark against an OpenAI-compatible endpoint"
    )
    parser.add_argument("--base-url", required=True, help="Endpoint base URL")
    parser.add_argument("--model", required=True, help="Model identifier")
    parser.add_argument(
        "--api-key", default="", help="API key (optional for endpoints without auth)"
    )
    parser.add_argument(
        "--output", default="data/amd_benchmark_results.json", help="Output JSON path"
    )
    parser.add_argument(
        "--concurrency",
        nargs="+",
        type=int,
        default=[1, 2, 4],
        help="Concurrency levels to test",
    )
    parser.add_argument(
        "--repeat", type=int, default=3, help="Repeat count per prompt type"
    )
    args = parser.parse_args()

    summary = run_benchmark(
        args.base_url, args.model, args.api_key, args.concurrency, args.repeat
    )
    save_benchmark_results(summary, args.output)
    print(f"Saved benchmark results to {args.output}")

    evidence = build_evidence_pack(summary)
    md = generate_benchmark_markdown(evidence)
    report_path = PROJECT_ROOT / "reports" / "amd_benchmark_report.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"Saved benchmark report to {report_path}")


if __name__ == "__main__":
    main()
