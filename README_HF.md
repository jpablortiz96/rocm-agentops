---
title: ROCm AgentOps Command Center
emoji: ⚡
colorFrom: red
colorTo: gray
sdk: docker
app_port: 8501
pinned: false
license: mit
short_description: AgentOps command center for trusted routing, auditability, and AMD/vLLM workflow evidence.
tags:
  - agentops
  - rocm
  - amd
  - streamlit
  - vllm
  - qwen
  - ai-agents
  - observability
  - incident-response
---

# ROCm AgentOps Command Center

ROCm AgentOps is an AgentOps command center that scores, routes, audits, and optimizes critical AI workflows on AMD GPUs.

## What This Space Runs

This public Space is configured to run safely without a live inference backend:

- `USE_MOCK_LLM=true` by default
- no API key required
- demo incidents and Command Center remain available
- example AMD benchmark evidence can be displayed when bundled artifacts are present
- deterministic scoring, routing, escalation packets, audit sealing, and War Room Packet export still work

That keeps the Space usable even when no external endpoint is connected.

## Connecting a Public AMD/vLLM Endpoint

If you want the Space to use a real public endpoint, add Space secrets such as:

```text
USE_MOCK_LLM=false
LLM_BASE_URL=https://YOUR_PUBLIC_AMD_VLLM_ENDPOINT/v1
LLM_MODEL=Qwen/Qwen2.5-7B-Instruct
LLM_API_KEY=
```

Notes:

- leave `LLM_API_KEY` empty if your endpoint does not require auth
- localhost endpoints do not work from Hugging Face Spaces unless the endpoint is running inside the same container
- for AMD Developer Cloud integration, use a public endpoint, secure proxy, or upload benchmark artifacts generated locally

## Runtime Behavior

- deterministic scoring always remains local
- advisory narrative can run in mock mode or against a live OpenAI-compatible endpoint
- benchmark evidence is treated as operational input, not just display telemetry
- live incidents are generated from workload evidence captured from AMD-backed inference infrastructure

## GitHub Repository

Full documentation, architecture notes, and release packaging live in the GitHub repository:

https://github.com/jpablortiz96/rocm-agentops
