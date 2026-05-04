# AMD Live Benchmark Report

**Run ID:** amd-bench-60fd7fd63f3e
**Timestamp:** 2026-05-04T21:22:39.771394Z
**Endpoint:** http://localhost:8000/v1
**Model:** Qwen/Qwen2.5-7B-Instruct
**Mock Mode:** OFF
**Verified:** Yes

## Summary
- **Total Requests:** 20
- **Successful:** 20
- **Failed:** 0
- **Benchmark Duration:** 22.50s

## Latency Metrics
- **Average:** 1502.98 ms
- **p50:** 1740.98 ms
- **p95:** 2456.03 ms

## Throughput
- **Estimated Total Tokens:** 8711
- **Estimated Tokens/sec:** 387.17
- **Concurrency Levels Tested:** [1, 2]

## AMD Evidence Claims
- This workflow can connect to an OpenAI-compatible model endpoint.
- Benchmark results were captured from the configured endpoint.
- Deterministic scoring remains local and does not consume GPU.
- LLM narrative steps can be batched and accelerated through GPU-backed serving.
- All benchmark requests succeeded with zero failures.

## Limitations
- Benchmarks reflect point-in-time endpoint performance.
- Token estimates are heuristic (len(text)/4) and not exact.
- Results may vary with different model sizes and quantization settings.

## Recommended Next Steps
- Run benchmarks at multiple concurrency levels to find throughput saturation.
- Compare results against baseline CPU-only inference.
- Profile with rocProf on MI300X to identify kernel-level optimizations.

## Detailed Request Results
| Request ID | Prompt Type | Success | Latency (ms) | Input Tok | Output Tok | Error |
|------------|-------------|---------|-------------|-----------|------------|-------|
| amd-bench-60fd7fd63f3e-planner-0 | planner | ✓ | 2230.78 | 84 | 537 | — |
| amd-bench-60fd7fd63f3e-critic-1 | critic | ✓ | 704.44 | 191 | 76 | — |
| amd-bench-60fd7fd63f3e-optimizer-2 | optimizer | ✓ | 2458.91 | 146 | 660 | — |
| amd-bench-60fd7fd63f3e-rocm_advisor-3 | rocm_advisor | ✓ | 1739.74 | 102 | 416 | — |
| amd-bench-60fd7fd63f3e-reporter-4 | reporter | ✓ | 510.43 | 80 | 82 | — |
| amd-bench-60fd7fd63f3e-planner-5 | planner | ✓ | 2455.88 | 84 | 576 | — |
| amd-bench-60fd7fd63f3e-critic-6 | critic | ✓ | 718.02 | 191 | 76 | — |
| amd-bench-60fd7fd63f3e-optimizer-7 | optimizer | ✓ | 1740.48 | 146 | 391 | — |
| amd-bench-60fd7fd63f3e-rocm_advisor-8 | rocm_advisor | ✓ | 1741.48 | 102 | 417 | — |
| amd-bench-60fd7fd63f3e-reporter-9 | reporter | ✓ | 513.60 | 80 | 79 | — |
| amd-bench-60fd7fd63f3e-critic-10 | critic | ✓ | 815.30 | 191 | 76 | — |
| amd-bench-60fd7fd63f3e-planner-11 | planner | ✓ | 2044.16 | 84 | 413 | — |
| amd-bench-60fd7fd63f3e-optimizer-12 | optimizer | ✓ | 2310.74 | 146 | 491 | — |
| amd-bench-60fd7fd63f3e-reporter-13 | reporter | ✓ | 553.46 | 80 | 82 | — |
| amd-bench-60fd7fd63f3e-rocm_advisor-14 | rocm_advisor | ✓ | 1945.42 | 102 | 412 | — |
| amd-bench-60fd7fd63f3e-critic-15 | critic | ✓ | 818.06 | 191 | 76 | — |
| amd-bench-60fd7fd63f3e-planner-16 | planner | ✓ | 1947.05 | 84 | 413 | — |
| amd-bench-60fd7fd63f3e-optimizer-17 | optimizer | ✓ | 2265.21 | 146 | 493 | — |
| amd-bench-60fd7fd63f3e-reporter-18 | reporter | ✓ | 497.95 | 80 | 85 | — |
| amd-bench-60fd7fd63f3e-rocm_advisor-19 | rocm_advisor | ✓ | 2048.50 | 102 | 448 | — |
