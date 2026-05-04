# AMD Live Benchmark Report

**Run ID:** amd-bench-30a30366422b
**Timestamp:** 2026-05-04T20:37:38.204275Z
**Endpoint:** http://localhost:8000/v1
**Model:** Qwen/Qwen2.5-1.5B-Instruct
**Mock Mode:** OFF
**Verified:** Yes

## Summary
- **Total Requests:** 20
- **Successful:** 20
- **Failed:** 0
- **Benchmark Duration:** 11.78s

## Latency Metrics
- **Average:** 783.17 ms
- **p50:** 765.88 ms
- **p95:** 1261.88 ms

## Throughput
- **Estimated Total Tokens:** 8343
- **Estimated Tokens/sec:** 708.26
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
| amd-bench-30a30366422b-planner-0 | planner | ✓ | 1011.07 | 84 | 501 | — |
| amd-bench-30a30366422b-critic-1 | critic | ✓ | 411.35 | 191 | 72 | — |
| amd-bench-30a30366422b-optimizer-2 | optimizer | ✓ | 814.60 | 146 | 307 | — |
| amd-bench-30a30366422b-rocm_advisor-3 | rocm_advisor | ✓ | 868.51 | 102 | 387 | — |
| amd-bench-30a30366422b-reporter-4 | reporter | ✓ | 328.07 | 80 | 130 | — |
| amd-bench-30a30366422b-planner-5 | planner | ✓ | 1076.21 | 84 | 533 | — |
| amd-bench-30a30366422b-critic-6 | critic | ✓ | 429.56 | 191 | 120 | — |
| amd-bench-30a30366422b-optimizer-7 | optimizer | ✓ | 705.79 | 146 | 356 | — |
| amd-bench-30a30366422b-rocm_advisor-8 | rocm_advisor | ✓ | 984.90 | 102 | 440 | — |
| amd-bench-30a30366422b-reporter-9 | reporter | ✓ | 512.94 | 80 | 142 | — |
| amd-bench-30a30366422b-critic-10 | critic | ✓ | 610.97 | 191 | 72 | — |
| amd-bench-30a30366422b-planner-11 | planner | ✓ | 1130.16 | 84 | 463 | — |
| amd-bench-30a30366422b-optimizer-12 | optimizer | ✓ | 1013.04 | 146 | 435 | — |
| amd-bench-30a30366422b-rocm_advisor-13 | rocm_advisor | ✓ | 830.12 | 102 | 359 | — |
| amd-bench-30a30366422b-reporter-14 | reporter | ✓ | 524.50 | 80 | 124 | — |
| amd-bench-30a30366422b-critic-15 | critic | ✓ | 507.36 | 191 | 91 | — |
| amd-bench-30a30366422b-optimizer-16 | optimizer | ✓ | 717.17 | 146 | 227 | — |
| amd-bench-30a30366422b-planner-17 | planner | ✓ | 1416.24 | 84 | 588 | — |
| amd-bench-30a30366422b-reporter-18 | reporter | ✓ | 517.05 | 80 | 119 | — |
| amd-bench-30a30366422b-rocm_advisor-19 | rocm_advisor | ✓ | 1253.76 | 102 | 465 | — |
