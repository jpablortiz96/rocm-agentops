# Build in Public Guide

## Suggested Launch Post

ROCm AgentOps Command Center is live.

It scores, routes, audits, and escalates critical AI workflows with deterministic controls first, selective model routing second, and audit-ready outputs throughout. The workflow can ingest business incidents, AMD-backed runtime signals, or both, then decide what stays deterministic, what gets a smaller-model summary, what deserves Qwen 7B on vLLM, and what must go to a human operator.

The current validated benchmark run used `Qwen/Qwen2.5-7B-Instruct` on an OpenAI-compatible AMD/vLLM stack with:

- 20/20 successful requests
- 1740.98 ms p50 latency
- 2456.03 ms p95 latency
- 387.17 estimated tokens/sec

Key design choice: deterministic scores, risk flags, and human review gates are never overwritten by LLM output.

#ROCm #AMDDeveloperCloud #AIatAMD #AgentOps #OpenSourceAI

## Suggested X / LinkedIn Short Post

Built ROCm AgentOps Command Center: a workflow assurance layer for AI operations on AMD GPUs.

It combines deterministic scoring, trust/risk analysis, policy guardrails, selective Qwen 7B routing on vLLM, escalation packets, an audit seal, and a War Room Packet export.

Validated benchmark run:
- 20/20 successful requests
- p50 1740.98 ms
- p95 2456.03 ms
- 387.17 tok/s estimated

Live incidents can be generated from benchmark, endpoint health, logs, and ROCm telemetry evidence.

#ROCm #AMDDeveloperCloud #AIatAMD #AgentOps #OpenSourceAI

## Telemetry Card Example

```md
# ROCm AgentOps AMD Run

- Model: Qwen/Qwen2.5-7B-Instruct
- Runtime: AMD-backed OpenAI-compatible vLLM endpoint
- Successful requests: 20/20
- p50 latency: 1740.98 ms
- p95 latency: 2456.03 ms
- Estimated throughput: 387.17 tokens/sec
- Top insight: AgentOps escalated low-trust security and hallucination incidents to human review while keeping lower-risk workflow steps deterministic.
- Baseline mismatch: A naive ranking over-prioritized user volume and underweighted evidence quality and trust.
```

## Technical Update Ideas

- explain why deterministic scores remain the source of operational control
- compare baseline ranking with policy-aware routing decisions
- show how benchmark p95 latency influences strategy recommendations
- share how Hybrid mode combines business incidents with AMD runtime evidence
- highlight War Room Packet contents as operational handoff artifacts
- explain why audit sealing matters for post-run integrity

## AMD Developer Cloud / ROCm Feedback Notes

Useful points to capture publicly:

- model startup time and endpoint responsiveness
- p50 vs p95 behavior under concurrency
- whether ROCm telemetry was easy to export with existing tooling
- how well vLLM served Qwen 7B under the benchmark mix
- what operational insights were possible from benchmark evidence alone
- what additional AMD/ROCm metrics would be useful for future workflow routing
