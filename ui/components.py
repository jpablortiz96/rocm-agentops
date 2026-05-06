"""Reusable Streamlit UI components."""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import plotly.express as px
import streamlit as st

from core.benchmark_schemas import AmdBenchmarkSummary
from core.benchmarking import build_evidence_pack
from core.config import config
from core.schemas import (
    AgentRunResult,
    AgentTraceEvent,
    BaselineDecision,
    Incident,
    OptimizationRecommendation,
    ROCmReadinessReport,
    TriageDecision,
)

THEME_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Space+Grotesk:wght@500;700&display=swap');

:root {
  --bg: #07090F;
  --bg-secondary: #0F1117;
  --card: #151A24;
  --border: rgba(255,255,255,0.08);
  --accent: #FF2A2A;
  --accent-secondary: #FF4D4D;
  --warning: #FF7A00;
  --success: #22C55E;
  --text: #FFFFFF;
  --text-secondary: #C7CDD9;
  --muted: #9CA3AF;
}

.stApp {
  background:
    radial-gradient(circle at top right, rgba(255,42,42,0.18), transparent 24%),
    radial-gradient(circle at 20% 20%, rgba(255,77,77,0.08), transparent 18%),
    linear-gradient(rgba(255,255,255,0.03) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255,255,255,0.03) 1px, transparent 1px),
    linear-gradient(180deg, #07090F 0%, #0B0F17 55%, #07090F 100%);
  background-size: auto, auto, 48px 48px, 48px 48px, auto;
  color: var(--text);
  font-family: 'Inter', system-ui, sans-serif;
}

h1, h2, h3, h4, h5, h6 {
  font-family: 'Space Grotesk', 'Inter', system-ui, sans-serif !important;
  color: var(--text) !important;
  letter-spacing: -0.02em;
}

p, li, div, span, label {
  color: var(--text-secondary);
}

[data-testid="stHeader"] {
  background: rgba(7,9,15,0.72);
}

[data-testid="stSidebar"] {
  background: rgba(15,17,23,0.96);
  border-right: 1px solid var(--border);
}

[data-testid="stSidebar"] * {
  color: var(--text-secondary) !important;
}

.block-container {
  padding-top: 1.5rem;
  padding-bottom: 2.75rem;
}

div[data-baseweb="tab-list"] {
  gap: 0.5rem;
}

button[data-baseweb="tab"] {
  background: rgba(255,255,255,0.03) !important;
  border: 1px solid var(--border) !important;
  border-radius: 999px !important;
  padding: 0.45rem 0.95rem !important;
  color: var(--text-secondary) !important;
  font-family: 'Inter', system-ui, sans-serif !important;
}

button[data-baseweb="tab"][aria-selected="true"] {
  background: linear-gradient(90deg, rgba(255,42,42,0.18), rgba(255,77,77,0.12)) !important;
  border-color: rgba(255,42,42,0.38) !important;
  color: var(--text) !important;
  box-shadow: 0 0 0 1px rgba(255,42,42,0.14), 0 12px 40px rgba(255,42,42,0.12);
}

.stButton>button, .stDownloadButton>button {
  background: linear-gradient(90deg, #FF2A2A 0%, #FF4D4D 100%);
  border: none;
  color: #FFFFFF;
  border-radius: 999px;
  padding: 0.6rem 1rem;
  font-weight: 700;
  box-shadow: 0 14px 40px rgba(255,42,42,0.22);
}

.stExpander {
  border: 1px solid var(--border) !important;
  background: rgba(21,26,36,0.92) !important;
  border-radius: 16px !important;
}

.stTextInput input, .stTextArea textarea, .stSelectbox div[data-baseweb="select"] > div, .stMultiSelect div[data-baseweb="select"] > div {
  background: rgba(15,17,23,0.98) !important;
  border: 1px solid var(--border) !important;
  border-radius: 14px !important;
  color: var(--text) !important;
}

div[data-testid="stDataFrame"] {
  border: 1px solid var(--border);
  border-radius: 18px;
  overflow: hidden;
  background: rgba(15,17,23,0.9);
}

div[data-testid="stDataFrame"] thead tr th {
  background: rgba(255,42,42,0.08) !important;
  color: var(--text) !important;
}

.hero-shell {
  position: relative;
  overflow: hidden;
  padding: 1.6rem 1.65rem 1.45rem 1.65rem;
  background:
    radial-gradient(circle at top right, rgba(255,42,42,0.18), transparent 28%),
    linear-gradient(180deg, rgba(21,26,36,0.98) 0%, rgba(15,17,23,0.98) 100%);
  border: 1px solid rgba(255,42,42,0.16);
  border-radius: 24px;
  box-shadow: 0 28px 90px rgba(0,0,0,0.28);
  margin-bottom: 1rem;
}

.hero-kicker {
  font-size: 0.78rem;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: #FF7A7A;
  margin-bottom: 0.6rem;
}

.hero-title {
  font-family: 'Space Grotesk', 'Inter', system-ui, sans-serif;
  font-size: 2.2rem;
  line-height: 1.05;
  font-weight: 700;
  color: var(--text);
  margin: 0 0 0.45rem 0;
}

.hero-subtitle {
  max-width: 980px;
  color: var(--text-secondary);
  font-size: 1rem;
  line-height: 1.55;
}

.runtime-badges {
  display: flex;
  flex-wrap: wrap;
  gap: 0.55rem;
  margin-top: 1rem;
}

.runtime-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  border-radius: 999px;
  padding: 0.45rem 0.8rem;
  font-size: 0.84rem;
  font-weight: 700;
  border: 1px solid var(--border);
  color: var(--text);
  background: rgba(255,255,255,0.03);
}

.badge-live { border-color: rgba(34,197,94,0.35); color: #B6F6C3; }
.badge-model { border-color: rgba(255,42,42,0.38); color: #FFD4D4; }
.badge-verified { border-color: rgba(255,77,77,0.35); color: #FFD6D6; }
.badge-audit { border-color: rgba(255,255,255,0.16); color: var(--text); }
.badge-warn { border-color: rgba(255,122,0,0.35); color: #FFD0A8; }

.section-shell {
  background: rgba(21,26,36,0.92);
  border: 1px solid var(--border);
  border-radius: 22px;
  padding: 1rem 1.05rem;
  box-shadow: 0 24px 80px rgba(0,0,0,0.18);
  margin-bottom: 1rem;
}

.cards-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 0.85rem;
  margin-bottom: 0.9rem;
}

.metric-card, .detail-card {
  min-height: 140px;
  border-radius: 22px;
  background: linear-gradient(180deg, rgba(21,26,36,0.98) 0%, rgba(15,17,23,0.98) 100%);
  border: 1px solid var(--border);
  box-shadow: 0 24px 80px rgba(0,0,0,0.18);
  padding: 1.05rem 1.1rem;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  gap: 0.5rem;
}

.metric-card.accent {
  border-color: rgba(255,42,42,0.26);
  box-shadow: 0 18px 65px rgba(255,42,42,0.10);
}

.metric-label, .detail-label {
  font-size: 0.92rem;
  line-height: 1.3;
  color: var(--muted);
  font-weight: 600;
}

.metric-value {
  font-family: 'Space Grotesk', 'Inter', system-ui, sans-serif;
  font-size: clamp(2.2rem, 4vw, 3rem);
  line-height: 1.0;
  color: var(--text);
  font-weight: 700;
}

.detail-value {
  font-family: 'Space Grotesk', 'Inter', system-ui, sans-serif;
  font-size: clamp(1.25rem, 2.1vw, 1.7rem);
  line-height: 1.2;
  color: var(--text);
  font-weight: 600;
  overflow-wrap: anywhere;
  word-break: break-word;
}

.metric-footnote, .detail-footnote {
  font-size: 0.86rem;
  line-height: 1.4;
  color: var(--text-secondary);
}

.status-pill {
  display: inline-flex;
  align-items: center;
  padding: 0.35rem 0.7rem;
  border-radius: 999px;
  font-size: 0.82rem;
  font-weight: 700;
  margin-right: 0.45rem;
}

.status-pass { background: rgba(34,197,94,0.12); color: #A7F3B7; border: 1px solid rgba(34,197,94,0.22); }
.status-warning { background: rgba(255,122,0,0.12); color: #FFD0A8; border: 1px solid rgba(255,122,0,0.22); }
.status-fail { background: rgba(255,42,42,0.12); color: #FFD4D4; border: 1px solid rgba(255,42,42,0.22); }
.status-neutral { background: rgba(255,255,255,0.06); color: var(--text-secondary); border: 1px solid var(--border); }

.subtle-note {
  color: var(--muted);
  font-size: 0.86rem;
}
</style>
"""


def render_header() -> None:
    st.set_page_config(page_title="ROCm AgentOps Command Center", page_icon=":fire:", layout="wide")
    st.markdown(THEME_CSS, unsafe_allow_html=True)
    st.markdown(
        """
        <div class="section-shell" style="padding: 0.95rem 1rem; margin-bottom: 1.1rem;">
          <div class="hero-kicker">Premium AMD-Inspired Control Plane</div>
          <div style="font-family: 'Space Grotesk', 'Inter', system-ui, sans-serif; font-size: 1.6rem; color: #FFFFFF; font-weight: 700;">
            ROCm AgentOps
          </div>
          <div class="subtle-note">Trusted orchestration, auditability, and performance routing for critical AI workflows on AMD GPUs.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar() -> Dict[str, Any]:
    with st.sidebar:
        st.header("Settings")
        mock_mode = st.toggle("Mock LLM Mode", value=config.is_mock(), help="Run without API keys")
        api_key = st.text_input("LLM API Key", value=config.LLM_API_KEY, type="password")
        base_url = st.text_input("Base URL", value=config.LLM_BASE_URL)
        model = st.text_input("Model", value=config.LLM_MODEL)
        report_mode = st.selectbox("Report Mode", ["Executive", "Engineer", "Audit"], index=0)
        st.divider()
        st.caption("ROCm AgentOps v0.1.0")
    return {
        "mock_mode": mock_mode,
        "api_key": api_key,
        "base_url": base_url,
        "model": model,
        "report_mode": report_mode,
    }


def render_incident_source_controls(
    *,
    source_mode: str,
    source_options: List[str],
    threshold_defaults: Dict[str, float],
) -> tuple[str, bool, Dict[str, float]]:
    st.markdown("### Incident Source")
    st.write(
        "Live incidents are generated from workload evidence captured from AMD-backed inference infrastructure: "
        "endpoint health, benchmark results, logs, and optional ROCm/GPU telemetry."
    )
    st.caption(
        "Hybrid mode combines benchmark/live workload incidents with business incident templates for end-to-end validation."
    )
    selected_mode = st.selectbox(
        "Incident Source",
        source_options,
        index=source_options.index(source_mode) if source_mode in source_options else 0,
        key="incident_source_mode",
    )
    default_probe_enabled = selected_mode in {"AMD Live Signals", "Hybrid"}
    if st.session_state.get("_live_probe_default_for_mode") != selected_mode:
        st.session_state["enable_live_endpoint_probe"] = default_probe_enabled
        st.session_state["_live_probe_default_for_mode"] = selected_mode
    enable_live_endpoint_probe = st.toggle(
        "Enable Live Endpoint Probe",
        value=st.session_state.get("enable_live_endpoint_probe", default_probe_enabled),
        help=(
            "Probes the configured OpenAI-compatible endpoint for live workload health. "
            "This is separate from Mock LLM narrative mode."
        ),
        key="enable_live_endpoint_probe",
    )
    with st.expander("Live Signal Thresholds", expanded=selected_mode != "Demo Dataset"):
        col1, col2 = st.columns(2)
        with col1:
            p95_latency_sla_ms = st.number_input(
                "p95 latency SLA threshold (ms)",
                min_value=100,
                value=int(threshold_defaults.get("p95_latency_sla_ms", 2500)),
                step=50,
                key="threshold_p95_latency_sla_ms",
            )
            minimum_success_rate = st.number_input(
                "minimum benchmark success rate",
                min_value=0.0,
                max_value=1.0,
                value=float(threshold_defaults.get("minimum_success_rate", 0.95)),
                step=0.01,
                format="%.2f",
                key="threshold_minimum_success_rate",
            )
        with col2:
            warning_threshold_pct = st.number_input(
                "warning threshold percentage",
                min_value=0.5,
                max_value=1.0,
                value=float(threshold_defaults.get("warning_threshold_pct", 0.90)),
                step=0.01,
                format="%.2f",
                key="threshold_warning_threshold_pct",
            )
            max_failed_requests = st.number_input(
                "max failed requests",
                min_value=0,
                value=int(threshold_defaults.get("max_failed_requests", 0)),
                step=1,
                key="threshold_max_failed_requests",
            )

    thresholds = {
        "p95_latency_sla_ms": float(p95_latency_sla_ms),
        "warning_threshold_pct": float(warning_threshold_pct),
        "minimum_success_rate": float(minimum_success_rate),
        "max_failed_requests": int(max_failed_requests),
    }
    return selected_mode, bool(enable_live_endpoint_probe), thresholds


def render_incident_source_panel(
    *,
    signal_summary: Optional[Dict[str, Any]],
) -> None:
    if not signal_summary:
        st.info("Live signal collection has not run yet for the selected source mode.")
        return

    st.markdown("### Signal Summary")
    if signal_summary.get("live_evidence_enabled"):
        st.markdown(_status_badge("Live Evidence Enabled", "pass"), unsafe_allow_html=True)

    endpoint_health = signal_summary.get("endpoint_health", "unavailable")
    endpoint_health_label = {
        "healthy": "Online",
        "degraded": "Degraded",
        "unavailable": "Offline",
        "skipped": "Skipped",
        "collector_error": "Collector Error",
    }.get(str(endpoint_health), str(endpoint_health).replace("_", " ").title())

    metric_cards = [
        {"label": "Endpoint Health", "value": endpoint_health_label, "note": "Live endpoint probe"},
        {"label": "Benchmark Availability", "value": "Yes" if signal_summary.get("benchmark_available") else "No", "note": "Benchmark artifacts detected"},
        {"label": "GPU Telemetry", "value": "Yes" if signal_summary.get("gpu_telemetry_available") else "No", "note": "ROCm metrics"},
        {"label": "Logs Availability", "value": "Yes" if signal_summary.get("logs_available") else "No", "note": "Configured log sources"},
        {"label": "Live Incidents", "value": str(signal_summary.get("live_incidents_generated", 0)), "note": "Generated from live signals"},
    ]
    render_metric_cards(metric_cards)
    details = signal_summary.get("details") or {}
    endpoint = details.get("endpoint") or {}
    benchmark = details.get("benchmark") or {}
    gpu_metrics = details.get("gpu_metrics") or {}
    logs = details.get("logs") or {}

    detail_cards = [
        {
            "label": "Endpoint Probe",
            "value": endpoint_health_label,
            "note": "Runtime health status",
        },
        {
            "label": "Probe Latency",
            "value": f"{endpoint.get('latency_ms', 0):.0f} ms" if endpoint.get("latency_ms") else "N/A",
            "note": "Tiny chat completion probe",
        },
        {
            "label": "Endpoint Model",
            "value": endpoint.get("model") or "N/A",
            "note": "Configured or detected model",
        },
        {
            "label": "Probe Response",
            "value": endpoint.get("probe_response_preview") or endpoint.get("skip_reason") or "N/A",
            "note": "Preview from the live probe",
        },
        {
            "label": "Benchmark Run ID",
            "value": benchmark.get("run_id", "N/A"),
            "note": "Latest benchmark artifact",
        },
        {
            "label": "GPU Snapshot",
            "value": (
                f"{gpu_metrics.get('utilization_pct', 'N/A')}% util / {gpu_metrics.get('memory_usage_pct', 'N/A')}% mem"
                if signal_summary.get("gpu_telemetry_available")
                else "Unavailable"
            ),
            "note": "Optional ROCm telemetry",
        },
    ]
    render_detail_cards(detail_cards)

    copyable_values = {
        "Endpoint Health": str(endpoint.get("endpoint_health", "N/A")),
        "Endpoint Error": str(endpoint.get("error", details.get("error", endpoint.get("skip_reason", "None")))),
        "Endpoint Status Code": str(endpoint.get("status_code") or endpoint.get("models_status_code") or "N/A"),
        "Endpoint Model": str(endpoint.get("model", "N/A")),
        "Endpoint Base URL": str(endpoint.get("base_url", details.get("runtime_context", {}).get("base_url", "N/A"))),
        "Probe Response": str(endpoint.get("probe_response_preview", "N/A")),
        "Benchmark Run ID": str(benchmark.get("run_id", "N/A")),
        "Benchmark Model": str(benchmark.get("model", "N/A")),
        "Missing Log Paths": ", ".join(logs.get("missing_paths", [])) or "None",
    }
    _render_copyable_details("Copyable Signal Details", copyable_values)

    if details.get("error"):
        st.warning(f"Live signal collection encountered an error: {details['error']}")
    elif endpoint.get("skip_reason"):
        st.caption(f"Endpoint probe note: {endpoint['skip_reason']}")
    elif endpoint.get("error"):
        st.caption(f"Endpoint probe note: {endpoint['error']}")

    missing_paths = logs.get("missing_paths", [])
    if missing_paths:
        st.caption("Unavailable log paths: " + ", ".join(missing_paths))

    if signal_summary.get("gpu_telemetry_available"):
        st.markdown("### GPU Telemetry")
        gpu_cards = [
            {"label": "GPU Util %", "value": gpu_metrics.get("utilization_pct", "N/A"), "note": "Current utilization"},
            {"label": "GPU Memory %", "value": gpu_metrics.get("memory_usage_pct", "N/A"), "note": "Current memory pressure"},
            {"label": "Temperature C", "value": gpu_metrics.get("temperature_c", "N/A"), "note": "Thermal snapshot"},
            {"label": "Power W", "value": gpu_metrics.get("power_w", "N/A"), "note": "Power draw"},
        ]
        render_detail_cards(gpu_cards)
        gpu_memory_pct = gpu_metrics.get("memory_usage_pct")
        if gpu_memory_pct is not None and float(gpu_memory_pct) >= 80.0:
            st.warning(f"GPU memory pressure near threshold: {float(gpu_memory_pct):.1f}%")
        with st.expander("Raw GPU Telemetry"):
            st.code(gpu_metrics.get("raw_output") or "No raw GPU telemetry available.", language="text")

    findings = signal_summary.get("findings", [])
    st.markdown("### Live Signal Findings")
    if findings:
        findings_df = pd.DataFrame(
            [
                {
                    "Signal": finding.get("label", "Unknown"),
                    "Status": str(finding.get("status", "info")).upper(),
                    "Severity": str(finding.get("severity", "info")).upper(),
                    "Summary": finding.get("summary", ""),
                    "Evidence": " | ".join(finding.get("evidence", [])),
                }
                for finding in findings
            ]
        )
        st.dataframe(findings_df, use_container_width=True, hide_index=True)
    else:
        st.info("No live signal findings were generated.")

    if signal_summary.get("no_incident_reason"):
        st.info(signal_summary["no_incident_reason"])


def render_overview(
    report: AgentRunResult,
    benchmark: Optional[AmdBenchmarkSummary],
    report_mode: str,
) -> None:
    st.markdown(_build_hero_html(report, benchmark), unsafe_allow_html=True)
    analytics = report.historical_analytics
    benchmark_success = (
        f"{benchmark.successful_requests}/{benchmark.total_requests}"
        if benchmark and benchmark.total_requests
        else "Unverified"
    )
    metric_cards = [
        {"label": "Incidents", "value": len(report.triage_results), "note": "Current run"},
        {"label": "Human Reviews", "value": len(report.escalation_packets), "note": "Escalation gates"},
        {
            "label": "Recommended Strategy",
            "value": report.recommended_strategy.strategy_name if report.recommended_strategy else "N/A",
            "note": "Compiler decision",
            "tone": "accent",
        },
        {
            "label": "Benchmark Success",
            "value": benchmark_success,
            "note": "Example AMD evidence" if benchmark and benchmark.artifact_origin == "example" else "AMD evidence",
        },
        {
            "label": "p95 Latency",
            "value": f"{benchmark.p95_latency_ms:.0f} ms" if benchmark else "N/A",
            "note": (
                "Example benchmark artifact"
                if benchmark and benchmark.artifact_origin == "example"
                else "Benchmark verified"
                if benchmark
                else "No benchmark"
            ),
        },
        {
            "label": "Estimated Cost Avoided",
            "value": f"${analytics.estimated_cost_avoided_vs_all_large_model_usd:.4f}" if analytics else "$0.0000",
            "note": "Vs all-large-model",
        },
    ]
    render_metric_cards(metric_cards)

    detail_cards = [
        {"label": "Run ID", "value": report.run_id, "note": "Workflow identifier"},
        {"label": "Model", "value": report.llm_runtime_info.get("model", "N/A"), "note": "Narrative model"},
        {"label": "Endpoint", "value": report.llm_runtime_info.get("base_url", "N/A"), "note": "Configured runtime"},
        {
            "label": "Benchmark Run ID",
            "value": benchmark.run_id if benchmark else "N/A",
            "note": "Example artifact reference" if benchmark and benchmark.artifact_origin == "example" else "AMD evidence reference",
        },
    ]
    render_detail_cards(detail_cards)
    _render_copyable_details(
        "Copyable Runtime Values",
        {
            "Run ID": report.run_id,
            "Model": report.llm_runtime_info.get("model", "N/A"),
            "Endpoint": report.llm_runtime_info.get("base_url", "N/A"),
            "Benchmark Run ID": benchmark.run_id if benchmark else "N/A",
        },
    )

    if analytics:
        st.markdown("### Historical Routing Analytics")
        analytics_cards = [
            {"label": "Deterministic Only", "value": f"{analytics.deterministic_only_pct:.1f}%", "note": "Current run routing"},
            {"label": "Small-Model Routes", "value": f"{analytics.small_model_pct:.1f}%", "note": "Qwen 1.5B paths"},
            {"label": "Large-Model Routes", "value": f"{analytics.large_model_pct:.1f}%", "note": "Qwen 7B paths"},
            {"label": "Human Review", "value": f"{analytics.human_review_pct:.1f}%", "note": "Owner gates"},
            {
                "label": "Latency Avoided",
                "value": f"{analytics.estimated_latency_avoided_vs_all_large_model_ms:.0f} ms",
                "note": "Vs all Qwen 7B",
            },
            {
                "label": "Cost Avoided",
                "value": f"${analytics.estimated_cost_avoided_vs_all_large_model_usd:.4f}",
                "note": "Vs all Qwen 7B",
            },
        ]
        render_metric_cards(analytics_cards)
        st.caption(analytics.summary)

    _render_report_mode_view(report, benchmark, report_mode, location="Overview")


def render_incidents(incidents: List[Incident]) -> None:
    st.subheader("Loaded Incidents")
    if not incidents:
        st.info("No incidents available for the selected source mode.")
        return

    rows = []
    for incident in incidents:
        rows.append(
            {
                "ID": incident.id,
                "Title": incident.title,
                "Source": incident.source,
                "System": incident.system,
                "Severity": incident.severity_hint.value if hasattr(incident.severity_hint, "value") else str(incident.severity_hint),
                "Status": incident.status.value if hasattr(incident.status, "value") else str(incident.status),
                "Location": incident.location,
                "Affected Users": incident.affected_users,
                "Revenue Impact (USD)": incident.revenue_impact_usd,
                "SLA Remaining (min)": incident.sla_minutes_remaining,
                "Evidence Count": len(incident.evidence),
            }
        )
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def render_triage_results(results: List[TriageDecision]) -> None:
    st.subheader("Triage Results")
    if not results:
        st.info("No triage results yet.")
        return

    rows = []
    for rank, result in enumerate(results, start=1):
        rows.append(
            {
                "Rank": rank,
                "Incident": result.incident_id,
                "Title": result.title,
                "System": result.system,
                "Severity": result.severity_hint,
                "Priority Score": result.priority_score,
                "Trust Score": result.trust_score,
                "Human Review Required": "Yes" if result.human_review_required else "No",
                "Recommended Action": result.recommended_action,
            }
        )
    df = pd.DataFrame(rows)
    st.dataframe(_style_triage_dataframe(df), use_container_width=True)
    fig = px.bar(
        df,
        x="Incident",
        y="Priority Score",
        color="Severity",
        title="Priority Score by Incident",
        color_discrete_sequence=["#FF2A2A", "#FF7A00", "#FF4D4D", "#9CA3AF"],
    )
    fig.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", font_color="#FFFFFF")
    st.plotly_chart(fig, use_container_width=True)


def render_baseline_comparison(
    baseline: List[BaselineDecision], agentops: List[TriageDecision]
) -> None:
    st.subheader("Baseline vs ROCm AgentOps")
    if not baseline or not agentops:
        st.info("No comparison data available.")
        return

    comparison_df = pd.DataFrame(
        {
            "Capability": [
                "Priority ranking",
                "Trust score",
                "Risk flags",
                "Human review escalation",
                "Trace replay",
                "Cost estimate",
                "Latency visibility",
                "Optimization recommendations",
                "AMD/ROCm readiness",
                "Final audit report",
            ],
            "Baseline Agent": ["Yes", "No", "No", "No", "No", "No", "No", "No", "No", "No"],
            "ROCm AgentOps": ["Yes", "Yes", "Yes", "Yes", "Yes", "Yes", "Yes", "Yes", "Yes", "Yes"],
        }
    )
    st.dataframe(comparison_df, use_container_width=True, hide_index=True)
    metric_cards = [
        {"label": "Highest Baseline Priority", "value": baseline[0].incident_id, "note": f"score {baseline[0].baseline_score}"},
        {"label": "Highest AgentOps Priority", "value": agentops[0].incident_id, "note": f"score {agentops[0].priority_score}"},
        {"label": "Human Review Gates", "value": sum(1 for decision in agentops if decision.human_review_required), "note": "Deterministic escalation"},
    ]
    render_detail_cards(metric_cards)


def render_agent_review(markdown_text: str, llm_info: Optional[Dict[str, Any]] = None) -> None:
    st.subheader("Agent Review")
    if llm_info:
        badges = "".join(
            [
                _status_badge(
                    "Real endpoint" if llm_info.get("narrative_mode") == "Real endpoint" else llm_info.get("narrative_mode", "Unknown"),
                    "pass" if llm_info.get("narrative_mode") == "Real endpoint" else "warning",
                ),
                _status_badge(
                    f"Fallbacks: {len(llm_info.get('errors', []))}",
                    "pass" if not llm_info.get("errors") else "warning",
                ),
            ]
        )
        st.markdown(badges, unsafe_allow_html=True)
        detail_cards = [
            {"label": "Mock Mode", "value": "ON" if llm_info.get("mock_mode") else "OFF", "note": "Narrative runtime"},
            {"label": "Model", "value": llm_info.get("model", "N/A"), "note": "Configured model"},
            {"label": "Base URL", "value": llm_info.get("base_url", "N/A"), "note": "Endpoint"},
            {"label": "Narrative Mode", "value": llm_info.get("narrative_mode", "N/A"), "note": "Observed runtime"},
        ]
        render_detail_cards(detail_cards)
        _render_copyable_details(
            "Copyable Runtime Details",
            {
                "Model": llm_info.get("model", "N/A"),
                "Base URL": llm_info.get("base_url", "N/A"),
            },
        )
        if llm_info.get("errors"):
            st.warning("LLM errors detected:\n- " + "\n- ".join(llm_info["errors"]))
    if markdown_text:
        st.markdown(markdown_text)


def render_command_center(report: AgentRunResult) -> None:
    st.subheader("Command Center")
    if not report.model_routes:
        st.info("Command Center data is not available for this run.")
        return

    st.markdown("### Workflow Compiler Summary")
    summary_cards = _build_command_center_summary_cards(report)
    render_metric_cards(summary_cards)
    with st.container(border=True):
        st.markdown(report.command_center_summary)

    st.markdown("### Model Router")
    st.dataframe(_style_model_router_dataframe(_build_model_router_dataframe(report)), use_container_width=True)
    st.caption(
        "`Human review packet only` means no model generation is required before human ownership. "
        "Deterministic/template estimates are local workflow timing estimates, not model inference latency."
    )

    st.markdown("### Strategy Simulator")
    st.dataframe(_style_strategy_dataframe(_build_strategy_dataframe(report)), use_container_width=True)
    if report.recommended_strategy:
        st.success(f"Recommended strategy: {report.recommended_strategy.strategy_name}")
        st.caption(report.recommended_strategy.rationale)

    st.markdown("### SLA Monitor")
    if report.sla_monitor_result:
        st.markdown(_status_badge(report.sla_monitor_result.status, _sla_tone(report.sla_monitor_result.status)), unsafe_allow_html=True)
        if report.sla_monitor_result.status == "FAIL":
            st.error(report.sla_monitor_result.summary_message)
        elif report.sla_monitor_result.status in {"WARN", "PASS_WITH_WARNING"}:
            st.warning(report.sla_monitor_result.summary_message)
        else:
            st.success(report.sla_monitor_result.summary_message)
        cols = st.columns(2)
        with cols[0]:
            st.write("**Violations**")
            if report.sla_monitor_result.violations:
                for violation in report.sla_monitor_result.violations:
                    st.write(f"- {violation}")
            else:
                st.write("- None")
        with cols[1]:
            st.write("**Mitigation**")
            for item in report.sla_monitor_result.recommended_mitigation:
                st.write(f"- {item}")

    st.markdown("### Policy Guardrails")
    if report.policy_compliance:
        st.markdown(
            _status_badge(
                report.policy_compliance.compliance_status,
                "pass" if report.policy_compliance.compliance_status == "COMPLIANT" else "warning",
            ),
            unsafe_allow_html=True,
        )
        st.caption(report.policy_compliance.summary)
        cols = st.columns(2)
        with cols[0]:
            loaded_df = pd.DataFrame(
                [
                    {"Policy ID": policy.policy_id, "Name": policy.name, "Enforcement": policy.enforcement}
                    for policy in report.policy_compliance.loaded_policies
                ]
            )
            st.write("**Loaded Policies**")
            st.dataframe(loaded_df, use_container_width=True, hide_index=True)
        with cols[1]:
            triggered_df = pd.DataFrame(
                [
                    {
                        "Policy ID": hit.policy_id,
                        "Name": hit.policy_name,
                        "Incident": hit.incident_id or "Global",
                        "Enforcement": hit.enforcement,
                    }
                    for hit in report.policy_compliance.triggered_policies
                ]
            )
            st.write("**Triggered Policies**")
            if triggered_df.empty:
                st.info("No policy hits were triggered.")
            else:
                st.dataframe(triggered_df, use_container_width=True, hide_index=True)

    st.markdown("### Escalation Packets")
    if report.escalation_packets:
        for packet in report.escalation_packets:
            with st.expander(f"{packet.incident_id} -> {packet.recipient_email}"):
                st.info("Demo packet only; no email was sent.")
                st.write(f"**Recipient:** {packet.recipient_name} ({packet.recipient_email})")
                st.write(f"**Slack Channel:** {packet.slack_channel}")
                st.write(f"**Subject:** {packet.subject}")
                if packet.policy_hits:
                    st.write("**Policy Hits:** " + ", ".join(packet.policy_hits))
                st.text_area(
                    f"Markdown Preview - {packet.incident_id}",
                    value=packet.markdown_body,
                    height=260,
                    key=f"packet_md_{packet.incident_id}",
                )
                col1, col2 = st.columns(2)
                col1.download_button(
                    label=f"Download {packet.incident_id} MD",
                    data=packet.markdown_body,
                    file_name=f"{packet.incident_id.lower()}_escalation.md",
                    mime="text/markdown",
                    key=f"download_md_{packet.incident_id}",
                )
                col2.download_button(
                    label=f"Download {packet.incident_id} EML",
                    data=packet.eml_content,
                    file_name=f"{packet.incident_id.lower()}_escalation.eml",
                    mime="message/rfc822",
                    key=f"download_eml_{packet.incident_id}",
                )

    st.markdown("### Audit Seal")
    if report.audit_seal:
        detail_cards = [
            {"label": "Audit ID", "value": report.audit_seal.audit_id, "note": "Tamper-evident identifier"},
            {"label": "Generated At", "value": report.audit_seal.generated_at, "note": "UTC timestamp"},
        ]
        render_detail_cards(detail_cards)
        st.code(report.audit_seal.sha256, language="text")
        st.caption(report.audit_seal.explanation)

    st.markdown("### Telemetry Card")
    if report.telemetry_card:
        st.text_area("Copyable Markdown", value=report.telemetry_card.markdown, height=240, key="telemetry_markdown")
        st.download_button(
            label="Download Telemetry Card (.md)",
            data=report.telemetry_card.markdown,
            file_name="rocm_agentops_telemetry_card.md",
            mime="text/markdown",
        )
        st.text_area("Suggested Post Text", value=report.telemetry_card.suggested_post_text, height=170, key="telemetry_post_text")
        st.caption(" ".join(report.telemetry_card.hashtags))

    st.markdown("### War Room Packet")
    if report.war_room_packet:
        st.write("Download a complete operational handoff bundle for this run.")
        st.download_button(
            label="Download War Room Packet (.zip)",
            data=report.war_room_packet.content,
            file_name=report.war_room_packet.file_name,
            mime=report.war_room_packet.media_type,
        )
        with st.expander("Included Files"):
            for item in report.war_room_packet.included_files:
                st.write(f"- {item}")


def render_trace(trace: List[AgentTraceEvent]) -> None:
    st.subheader("Agent Trace")
    if not trace:
        st.info("No trace available.")
        return
    df = pd.DataFrame(
        [
            {
                "Agent": event.agent_name,
                "Step": event.step_name,
                "Latency (ms)": event.latency_ms,
                "Status": event.status,
                "Input": event.input_summary[:120],
                "Output": event.output_summary[:120],
                "Estimated Cost": f"${event.estimated_cost_usd:.4f}",
            }
            for event in trace
        ]
    )
    st.dataframe(df, use_container_width=True, hide_index=True)
    df["Task"] = df["Agent"] + " - " + df["Step"]
    fig = px.bar(
        df,
        x="Latency (ms)",
        y="Task",
        color="Status",
        orientation="h",
        title="Agent Step Latencies",
        color_discrete_map={"success": "#22C55E", "warning": "#FF7A00", "error": "#FF2A2A"},
    )
    fig.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", font_color="#FFFFFF")
    st.plotly_chart(fig, use_container_width=True)


def render_optimizations(opts: List[OptimizationRecommendation]) -> None:
    st.subheader("Optimization Recommendations")
    if not opts:
        st.info("No optimizations suggested.")
        return
    for opt in opts:
        with st.expander(f"{opt.title} ({opt.category}, {opt.estimated_impact} impact)"):
            if opt.description:
                st.write(opt.description)
            if opt.recommendation:
                st.write(f"**Recommendation:** {opt.recommendation}")
            if opt.expected_benefit:
                st.write(f"**Expected Benefit:** {opt.expected_benefit}")
            if opt.complexity:
                st.write(f"**Complexity:** {opt.complexity}")
            if opt.action_items:
                st.write("**Actions:**")
                for action in opt.action_items:
                    st.write(f"- {action}")


def render_rocm_report(report: Optional[ROCmReadinessReport]) -> None:
    st.subheader("ROCm Readiness")
    if not report:
        st.info("No ROCm readiness report available.")
        return
    st.write(f"**Summary:** {report.summary}")
    st.write(f"**Estimated Impact:** {report.estimated_impact}")
    if report.gpu_relevant_steps:
        st.write(f"**GPU Relevant Steps:** {', '.join(report.gpu_relevant_steps)}")
    if report.rocm_optimizations:
        st.write("**ROCm Optimizations:**")
        for item in report.rocm_optimizations:
            st.write(f"- {item}")
    if report.batching_opportunities:
        st.write("**Batching Opportunities:**")
        for item in report.batching_opportunities:
            st.write(f"- {item}")
    if report.limitations:
        st.write("**Limitations:**")
        for item in report.limitations:
            st.write(f"- {item}")


def render_amd_live_evidence(benchmark: Optional[AmdBenchmarkSummary]) -> None:
    st.subheader("AMD Live Evidence")
    if benchmark is None:
        st.warning("No verified AMD benchmark loaded yet.")
        st.markdown(
            "Run the AMD/vLLM benchmark harness against the target endpoint and attach the resulting benchmark artifact to enable verified evidence in this view."
        )
        return

    verified = benchmark.successful_requests > 0
    if benchmark.artifact_origin == "example":
        st.info(
            "Showing the bundled example benchmark artifact. Connect a live AMD/vLLM endpoint or upload refreshed artifacts to replace this example with current runtime evidence."
        )
    st.markdown(
        _status_badge("Benchmark Verified" if verified else "Benchmark Unverified", "pass" if verified else "warning"),
        unsafe_allow_html=True,
    )
    metric_cards = [
        {"label": "Successful", "value": benchmark.successful_requests, "note": "Requests completed"},
        {"label": "Failed", "value": benchmark.failed_requests, "note": "Requests failed"},
        {"label": "Avg Latency", "value": f"{benchmark.avg_latency_ms:.0f} ms" if verified else "N/A", "note": "Mean response time"},
        {"label": "p50 Latency", "value": f"{benchmark.p50_latency_ms:.0f} ms" if verified else "N/A", "note": "Median response time"},
        {"label": "p95 Latency", "value": f"{benchmark.p95_latency_ms:.0f} ms" if verified else "N/A", "note": "Tail latency"},
        {"label": "Tokens / sec", "value": f"{benchmark.estimated_tokens_per_second:.1f}" if verified else "N/A", "note": "Estimated throughput"},
    ]
    render_metric_cards(metric_cards)

    detail_cards = [
        {"label": "Run ID", "value": benchmark.run_id, "note": "Benchmark identifier"},
        {
            "label": "Artifact Source",
            "value": "Bundled example artifact" if benchmark.artifact_origin == "example" else "Submitted benchmark artifact",
            "note": "Evidence provenance",
        },
        {"label": "Model", "value": benchmark.model, "note": "Benchmarked model"},
        {"label": "Endpoint", "value": benchmark.endpoint_base_url, "note": "Target endpoint"},
        {"label": "Concurrency Levels", "value": ", ".join(str(item) for item in benchmark.concurrency_levels), "note": "Test profile"},
    ]
    render_detail_cards(detail_cards)
    _render_copyable_details(
        "Copyable Benchmark Details",
        {
            "Run ID": benchmark.run_id,
            "Model": benchmark.model,
            "Endpoint": benchmark.endpoint_base_url,
            "Benchmark JSON Path": "data/amd_benchmark_results.json",
        },
    )

    rows = []
    for result in benchmark.request_results:
        rows.append(
            {
                "Request ID": result.request_id,
                "Prompt Type": result.prompt_type,
                "Success": result.success,
                "Latency (ms)": result.latency_ms,
                "Input Tok": result.estimated_input_tokens,
                "Output Tok": result.estimated_output_tokens,
                "Error": result.error or "-",
            }
        )
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    st.download_button(
        label="Download Benchmark JSON",
        data=json.dumps(benchmark.model_dump(mode="json"), indent=2),
        file_name="amd_benchmark_results.json",
        mime="application/json",
    )

    report_path = Path("reports/amd_benchmark_report.md")
    if report_path.exists():
        st.download_button(
            label="Download Benchmark Report (MD)",
            data=report_path.read_text(encoding="utf-8"),
            file_name="amd_benchmark_report.md",
            mime="text/markdown",
        )

    evidence = build_evidence_pack(benchmark)
    if verified:
        st.markdown("### AMD Evidence Claims")
        for claim in evidence.amd_claims:
            st.write(f"- {claim}")
    else:
        st.markdown("### Limitations")
        for limitation in evidence.limitations:
            st.write(f"- {limitation}")


def render_final_report(
    report: AgentRunResult,
    report_mode: str,
    benchmark: Optional[AmdBenchmarkSummary] = None,
) -> None:
    st.subheader("Final Report")
    summary_cards = [
        {"label": "Incidents", "value": len(report.triage_results), "note": "Processed"},
        {"label": "Trace Events", "value": len(report.trace), "note": "Workflow trace"},
        {"label": "Escalation Packets", "value": len(report.escalation_packets), "note": "Operational handoffs"},
        {
            "label": "Policy Hits",
            "value": len(report.policy_compliance.triggered_policies) if report.policy_compliance else 0,
            "note": "Guardrail triggers",
        },
    ]
    render_metric_cards(summary_cards)
    _render_report_mode_view(report, benchmark, report_mode, location="Final Report")
    with st.expander("Full Markdown Report", expanded=False):
        st.markdown(report.final_report_markdown)
    st.download_button(
        label="Download Markdown Report",
        data=report.final_report_markdown,
        file_name="rocm_agentops_report.md",
        mime="text/markdown",
    )


def render_metric_cards(cards: List[Dict[str, Any]]) -> None:
    _render_native_card_grid(cards, variant="metric")


def render_detail_cards(cards: List[Dict[str, Any]]) -> None:
    _render_native_card_grid(cards, variant="detail")


def _render_report_mode_view(
    report: AgentRunResult,
    benchmark: Optional[AmdBenchmarkSummary],
    report_mode: str,
    *,
    location: str,
) -> None:
    st.markdown(f"### {report_mode} View")
    if report_mode == "Executive":
        detail_cards = [
            {"label": "Recommended Strategy", "value": report.recommended_strategy.strategy_name if report.recommended_strategy else "N/A", "note": "Primary recommendation"},
            {"label": "Escalation Count", "value": len(report.escalation_packets), "note": "Human-review gates"},
            {
                "label": "Benchmark Success",
                "value": f"{benchmark.successful_requests}/{benchmark.total_requests}" if benchmark else "N/A",
                "note": "Example AMD evidence" if benchmark and benchmark.artifact_origin == "example" else "AMD evidence",
            },
            {"label": "Cost Avoided", "value": f"${report.historical_analytics.estimated_cost_avoided_vs_all_large_model_usd:.4f}" if report.historical_analytics else "$0.0000", "note": "Vs all-large-model"},
        ]
        render_detail_cards(detail_cards)
        st.write("**Top Incidents**")
        for decision in report.triage_results[:3]:
            st.write(f"- {decision.incident_id}: priority {decision.priority_score}, trust {decision.trust_score}, action {decision.recommended_action}")
    elif report_mode == "Engineer":
        detail_cards = [
            {"label": "Trace Events", "value": len(report.trace), "note": "Workflow trace depth"},
            {"label": "Model Routes", "value": len(report.model_routes), "note": "Compiled execution plan"},
            {"label": "Benchmark p95", "value": f"{benchmark.p95_latency_ms:.2f} ms" if benchmark else "N/A", "note": "Latency evidence"},
            {"label": "Policy Hits", "value": len(report.policy_compliance.triggered_policies) if report.policy_compliance else 0, "note": "Triggered guardrails"},
        ]
        render_detail_cards(detail_cards)
        st.write("**Optimization Recommendations**")
        for optimization in report.optimizations[:3]:
            st.write(f"- {optimization.title}")
    else:
        detail_cards = [
            {"label": "Policy Compliance", "value": report.policy_compliance.compliance_status if report.policy_compliance else "N/A", "note": "Guardrail outcome"},
            {"label": "Human Review Gates", "value": len(report.escalation_packets), "note": "Audit boundary"},
            {"label": "Audit Seal", "value": report.audit_seal.audit_id if report.audit_seal else "N/A", "note": "Tamper-evident hash"},
            {"label": "SLA Status", "value": report.sla_monitor_result.status if report.sla_monitor_result else "N/A", "note": "Run readiness"},
        ]
        render_detail_cards(detail_cards)
        st.write("**Deterministic vs LLM Boundary**")
        st.write("- Deterministic scoring owns priority, confidence, trust, action, and risk flags.")
        st.write("- LLMs only support narrative, critique, and reporting.")
    st.caption(f"{location} is currently filtered for the {report_mode.lower()} audience.")


def _build_hero_html(report: AgentRunResult, benchmark: Optional[AmdBenchmarkSummary]) -> str:
    narrative_mode = report.llm_runtime_info.get("narrative_mode", "Unknown")
    model = report.llm_runtime_info.get("model", "Unknown")
    fallback_count = len(report.llm_runtime_info.get("errors", []))
    badges = [
        ("Live AMD Endpoint" if narrative_mode == "Real endpoint" else narrative_mode, "live" if narrative_mode == "Real endpoint" else "warn"),
        (model, "model"),
        ("Benchmark Verified" if benchmark and benchmark.successful_requests > 0 else "Benchmark Pending", "verified" if benchmark and benchmark.successful_requests > 0 else "warn"),
        ("Audit Seal Enabled" if report.audit_seal else "Audit Seal Pending", "audit"),
        (f"Fallbacks: {fallback_count}", "warn" if fallback_count else "live"),
    ]
    badges_html = "".join(
        f'<span class="runtime-badge badge-{tone}">{html.escape(str(label))}</span>'
        for label, tone in badges
    )
    return f"""
    <div class="hero-shell">
      <div class="hero-kicker">ROCm AgentOps Premium Runtime</div>
      <div class="hero-title">ROCm AgentOps Command Center</div>
      <div class="hero-subtitle">
        Trusted orchestration, auditability, and performance routing for critical AI workflows on AMD GPUs.
      </div>
      <div class="runtime-badges">{badges_html}</div>
    </div>
    """


def _render_native_card_grid(cards: List[Dict[str, Any]], *, variant: str) -> None:
    if not cards:
        return

    columns_per_row = 4 if variant == "metric" else 3
    for start in range(0, len(cards), columns_per_row):
        row = cards[start : start + columns_per_row]
        columns = st.columns(len(row))
        for column, card in zip(columns, row):
            label = str(card.get("label", ""))
            value = str(card.get("value", ""))
            note = str(card.get("note", ""))
            with column:
                with st.container(border=True):
                    if variant == "metric":
                        st.metric(label=label, value=value, help=note or None)
                        if note:
                            st.caption(note)
                    else:
                        st.caption(label)
                        st.write(value)
                        if note:
                            st.caption(note)


def _render_copyable_details(title: str, values: Dict[str, str]) -> None:
    with st.expander(title):
        for label, value in values.items():
            st.write(f"**{label}**")
            st.code(value, language="text")


def _build_model_router_dataframe(report: AgentRunResult) -> pd.DataFrame:
    rows = []
    for route in report.model_routes:
        if route.selected_execution_mode == "deterministic_only" or route.recommended_model == "Human review packet only":
            latency_label = f"{route.expected_latency_ms:.0f} (deterministic/template estimate)"
        elif route.recommended_model == "Qwen/Qwen2.5-1.5B-Instruct":
            latency_label = f"{route.expected_latency_ms:.0f} (Qwen 1.5B estimate)"
        else:
            latency_label = f"{route.expected_latency_ms:.0f} (Qwen 7B benchmark estimate)"
        rows.append(
            {
                "Incident": route.incident_id,
                "Title": route.title,
                "Risk Tier": route.risk_tier,
                "Execution Mode": route.selected_execution_mode,
                "Recommended Model": route.recommended_model,
                "Expected Latency (ms)": latency_label,
                "Estimated Cost": f"${route.expected_cost_usd:.4f}",
                "Owner": route.owner_name,
                "Owner Email": route.owner_email,
                "Reason": route.reason,
            }
        )
    return pd.DataFrame(rows)


def _build_strategy_dataframe(report: AgentRunResult) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Strategy": strategy.strategy_name,
                "Estimated Latency (ms)": f"{strategy.total_estimated_latency_ms:.0f}",
                "p95 Risk": strategy.p95_latency_risk,
                "Estimated Cost": f"${strategy.estimated_cost_usd:.4f}",
                "Quality Score": f"{strategy.expected_quality_score:.1f}",
                "Risk Coverage": f"{strategy.risk_coverage_score:.1f}",
                "Human Reviews": strategy.human_review_count,
                "Model Calls": strategy.model_calls,
                "Recommended": "Yes" if strategy.recommended else "No",
            }
            for strategy in report.strategy_results
        ]
    )


def _build_command_center_summary_cards(report: AgentRunResult) -> List[Dict[str, Any]]:
    deterministic_count = sum(1 for route in report.model_routes if route.selected_execution_mode == "deterministic_only")
    small_count = sum(1 for route in report.model_routes if route.selected_execution_mode == "small_model")
    large_count = sum(1 for route in report.model_routes if route.selected_execution_mode == "large_model")
    human_review_count = sum(1 for route in report.model_routes if route.selected_execution_mode == "human_review")
    return [
        {"label": "Deterministic Routes", "value": deterministic_count, "note": "Template/local paths"},
        {"label": "Small-Model Routes", "value": small_count, "note": "Qwen 1.5B summaries"},
        {"label": "Large-Model Routes", "value": large_count, "note": "Qwen 7B critiques"},
        {"label": "Human Review Gates", "value": human_review_count, "note": "Owner escalation"},
    ]


def _style_model_router_dataframe(df: pd.DataFrame) -> pd.io.formats.style.Styler:
    def highlight_row(row: pd.Series) -> List[str]:
        if row["Risk Tier"] == "critical":
            return ["background-color: rgba(255,42,42,0.12); color: #FFFFFF;"] * len(row)
        if row["Execution Mode"] == "deterministic_only":
            return ["background-color: rgba(255,255,255,0.03);"] * len(row)
        if row["Recommended Model"] == "Qwen/Qwen2.5-7B-Instruct":
            return ["background-color: rgba(255,77,77,0.08);"] * len(row)
        return [""] * len(row)

    return df.style.apply(highlight_row, axis=1).hide(axis="index")


def _style_strategy_dataframe(df: pd.DataFrame) -> pd.io.formats.style.Styler:
    def highlight_row(row: pd.Series) -> List[str]:
        if row["Recommended"] == "Yes":
            return ["background-color: rgba(34,197,94,0.08); color: #FFFFFF;"] * len(row)
        return [""] * len(row)

    return df.style.apply(highlight_row, axis=1).hide(axis="index")


def _style_triage_dataframe(df: pd.DataFrame) -> pd.io.formats.style.Styler:
    def highlight_row(row: pd.Series) -> List[str]:
        if row["Human Review Required"] == "Yes":
            return ["background-color: rgba(255,42,42,0.10); color: #FFFFFF;"] * len(row)
        return [""] * len(row)

    return df.style.apply(highlight_row, axis=1).hide(axis="index")


def _status_badge(label: str, tone: str) -> str:
    tone_class = {
        "pass": "status-pass",
        "warning": "status-warning",
        "fail": "status-fail",
    }.get(tone, "status-neutral")
    return f'<span class="status-pill {tone_class}">{html.escape(label)}</span>'


def _sla_tone(status: str) -> str:
    if status == "FAIL":
        return "fail"
    if status in {"WARN", "PASS_WITH_WARNING"}:
        return "warning"
    return "pass"
