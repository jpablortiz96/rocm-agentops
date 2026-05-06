# Deployment Guide

## Overview

ROCm AgentOps supports three practical deployment modes:

1. local Streamlit execution
2. AMD Developer Cloud endpoint mode with a live vLLM backend
3. Hugging Face Spaces deployment using Docker

The safest public default is mock narrative mode with bundled example evidence. Deterministic scoring, Command Center, Audit Seal, War Room Packet, and report generation remain available even without a live endpoint.

## Local Deployment

### Environment setup

Windows PowerShell:

```powershell
python -m venv venv
venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

macOS / Linux:

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

### Local configuration

Use `.env.example` as a starting point:

```dotenv
USE_MOCK_LLM=true
LLM_API_KEY=
LLM_BASE_URL=http://localhost:8000/v1
LLM_MODEL=Qwen/Qwen2.5-7B-Instruct
```

- leave `LLM_API_KEY` empty for local vLLM endpoints without authentication
- keep `USE_MOCK_LLM=true` unless you are actively connecting a real endpoint

## AMD Developer Cloud Endpoint Mode

### Workflow

1. Start an OpenAI-compatible vLLM endpoint on your AMD environment.
2. If the endpoint is not public, forward it locally with SSH.
3. Set the Base URL and Model in the Streamlit sidebar.
4. Disable Mock Mode.
5. Run the workflow and, if needed, refresh the benchmark artifact.

Example SSH tunnel:

```bash
ssh -L 8000:127.0.0.1:8000 USER@YOUR_HOST
```

Example runtime values:

- Base URL: `http://localhost:8000/v1`
- Model: `Qwen/Qwen2.5-7B-Instruct`

### Refreshing benchmark evidence

```bash
python scripts/health_check_endpoint.py --base-url "http://localhost:8000/v1"
python scripts/run_amd_benchmark.py --base-url "http://localhost:8000/v1" --model "Qwen/Qwen2.5-7B-Instruct" --concurrency 1 2 --repeat 2 --output "data/amd_benchmark_results.json"
python scripts/generate_evidence_pack.py --input "data/amd_benchmark_results.json" --output "reports/amd_evidence_pack.md"
```

### Capturing ROCm telemetry

Run on the AMD instance:

```bash
python scripts/collect_amd_runtime_signals.py --output amd_runtime_signals.json
```

Copy locally:

```bash
scp root@YOUR_HOST:/root/amd_runtime_signals.json data/amd_runtime_signals.json
```

## Hugging Face Spaces Deployment

### Recommended public mode

For a public Space, use:

- `USE_MOCK_LLM=true`
- demo dataset or Hybrid mode
- bundled example benchmark artifact
- no API key unless connecting a real external endpoint

This keeps the Space functional without requiring a reachable localhost endpoint.

### Steps

1. Create a new Hugging Face Space.
2. Select `Docker` as the SDK.
3. Push this repository to the Space.
4. Copy `README_HF.md` into `README.md` in the Space repo so Hugging Face can read the required YAML header.
5. The container starts Streamlit on port `8501`.

### Optional Space secrets

```text
USE_MOCK_LLM=false
LLM_BASE_URL=https://YOUR_PUBLIC_AMD_VLLM_ENDPOINT/v1
LLM_MODEL=Qwen/Qwen2.5-7B-Instruct
LLM_API_KEY=
```

### Important limitation

`http://localhost:8000/v1` will not work from Hugging Face Spaces unless the inference server is running inside the same container. For AMD Developer Cloud integration from a Space, use:

- a public HTTPS endpoint
- a secure proxy or VPN path
- or locally generated benchmark artifacts uploaded into the repo

## GitHub Push Checklist

Before pushing:

1. confirm `.env` is not tracked
2. confirm `.streamlit/secrets.toml` is not tracked
3. confirm internal context notes are not tracked
4. confirm `data/amd_runtime_signals.json` is not tracked
5. confirm local report ZIPs are not tracked
6. confirm no private IPs or local file paths were added to docs

Recommended commands:

```bash
git status
git add README.md Dockerfile .dockerignore .gitignore .env.example docs/ app.py core/benchmarking.py core/benchmark_schemas.py core/config.py ui/components.py workflows/incident_triage_workflow.py
git commit -m "Prepare public release and Hugging Face deployment"
git push origin main
```

## Troubleshooting

### Space loads but no live endpoint is available

Expected in public mode. Keep Mock Mode enabled and rely on the bundled example benchmark artifact or local uploads.

### Live signal probe shows Offline

Check:

- Base URL
- model name
- network reachability
- whether the endpoint is public or tunneled correctly

### AMD benchmark is missing in the UI

Ensure either:

- `data/amd_benchmark_results.json` exists locally, or
- `data/amd_benchmark_results.example.json` is present for public/demo use

### GPU telemetry does not appear

`data/amd_runtime_signals.json` is optional. The app should continue without it.
