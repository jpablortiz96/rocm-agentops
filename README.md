# ROCm AgentOps

**Observability, Trust, and Optimization for AI Agents running on AMD / ROCm**

A lightweight AgentOps platform MVP built for the AMD Developer Hackathon.

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run the app (mock mode works without API keys)
streamlit run app.py
```

## Using a Real LLM

Copy `.env.example` to `.env` and fill in your credentials:

```bash
cp .env.example .env
```

Edit `.env`:

```
LLM_MOCK_MODE=false
LLM_API_KEY=sk-...
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini
```

The client is OpenAI-compatible, so you can point it to vLLM, TGI, or any AMD Cloud endpoint.

## Project Structure

```
rocm-agentops/
  app.py                          # Streamlit entrypoint
  requirements.txt
  README.md
  .env.example
  data/
    sample_incidents.json         # Demo incident data
  core/
    schemas.py                    # Pydantic models
    config.py                     # Settings
    llm_client.py                 # OpenAI-compatible client + mock mode
    scoring.py                    # Confidence/trust scoring
    tracing.py                    # Agent trace builder
    report_builder.py             # Markdown / JSON reports
  agents/
    planner_agent.py
    triage_agent.py
    critic_agent.py
    optimizer_agent.py
    rocm_advisor_agent.py
    reporter_agent.py
  workflows/
    incident_triage_workflow.py   # End-to-end orchestration
  ui/
    components.py                 # Reusable Streamlit components
```

## Features (MVP)

- **Incident Triage Agent** with priority ranking and reasoning
- **Trust / Confidence Scoring** with deterministic heuristics
- **Agent Trace Timeline** for observability
- **Cost & Latency Estimates**
- **Optimization Recommendations**
- **ROCm / AMD Readiness Report**
- **Downloadable Reports** (Markdown + JSON)
- **Mock LLM Mode** for zero-dependency demos

## AMD Live Benchmark Integration

The app includes scripts to benchmark against an AMD Developer Cloud OpenAI-compatible endpoint.

```bash
# 1. Health-check the endpoint
python scripts/health_check_endpoint.py --base-url http://YOUR_AMD_ENDPOINT:8000/v1

# 2. Run the benchmark
python scripts/run_amd_benchmark.py \
  --base-url http://YOUR_AMD_ENDPOINT:8000/v1 \
  --model Qwen/Qwen2.5-7B-Instruct \
  --concurrency 1 2 4 \
  --repeat 3

# 3. Generate evidence pack markdown
python scripts/generate_evidence_pack.py \
  --input data/amd_benchmark_results.json \
  --output reports/amd_evidence_pack.md
```

After running the benchmark, reload the Streamlit app to see metrics in the **AMD Live Evidence** tab.

## Deployment

The app is deployable to **Hugging Face Spaces** using the standard Streamlit Space template.

## License

MIT (Hackathon MVP)
