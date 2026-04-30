"""Reusable Streamlit UI components."""

from typing import List

import pandas as pd
import plotly.express as px
import streamlit as st

from core.schemas import (
    AgentTrace,
    FinalReport,
    Incident,
    OptimizationRecommendation,
    ROCmReadinessReport,
    TriageResult,
)


def render_header():
    st.set_page_config(page_title="ROCm AgentOps", page_icon="🤖", layout="wide")
    st.title("🤖 ROCm AgentOps")
    st.markdown(
        "**Observability, Trust, and Optimization for AI Agents running on AMD / ROCm**"
    )
    st.divider()


def render_sidebar():
    with st.sidebar:
        st.header("Settings")
        mock_mode = st.toggle("Mock LLM Mode", value=True, help="Run without API keys")
        api_key = st.text_input("LLM API Key", value="", type="password")
        base_url = st.text_input("Base URL", value="https://api.openai.com/v1")
        model = st.text_input("Model", value="gpt-4o-mini")
        st.divider()
        st.caption("ROCm AgentOps v0.1.0")
    return {"mock_mode": mock_mode, "api_key": api_key, "base_url": base_url, "model": model}


def render_incidents(incidents: List[Incident]):
    st.subheader("📋 Loaded Incidents")
    if not incidents:
        st.info("No incidents loaded.")
        return
    df = pd.DataFrame([i.model_dump() for i in incidents])
    important_cols = [
        "id",
        "title",
        "system",
        "severity_hint",
        "status",
        "location",
        "affected_users",
        "revenue_impact_usd",
        "sla_minutes_remaining",
        "evidence",
    ]
    display_cols = [c for c in important_cols if c in df.columns]
    st.dataframe(df[display_cols], use_container_width=True)


def render_triage_results(results: List[TriageResult]):
    st.subheader("🚦 Triage Results")
    if not results:
        st.info("No triage results yet.")
        return
    df = pd.DataFrame([r.model_dump() for r in results])
    st.dataframe(df, use_container_width=True)

    # Bar chart of confidence scores
    fig = px.bar(
        df,
        x="incident_id",
        y="confidence_score",
        color="priority_rank",
        title="Confidence Score by Incident",
        labels={"confidence_score": "Confidence", "incident_id": "Incident"},
    )
    st.plotly_chart(fig, use_container_width=True)


def render_trace(trace: AgentTrace):
    st.subheader("🔍 Agent Trace Timeline")
    if not trace.steps:
        st.info("No trace available.")
        return
    df = pd.DataFrame(
        [
            {
                "Step": s.step_name,
                "Agent": s.agent_name,
                "Status": s.status,
                "Latency (ms)": s.latency_ms,
            }
            for s in trace.steps
        ]
    )
    st.dataframe(df, use_container_width=True)

    fig = px.timeline(
        df,
        x_start=df.index,  # dummy; we use index for ordering
        x_end=df.index + df["Latency (ms)"] / 1000,
        y="Agent",
        color="Status",
        title="Agent Step Latencies",
    )
    st.plotly_chart(fig, use_container_width=True)


def render_optimizations(opts: List[OptimizationRecommendation]):
    st.subheader("⚡ Optimization Recommendations")
    if not opts:
        st.info("No optimizations suggested.")
        return
    for o in opts:
        with st.expander(f"{o.title} ({o.category}, {o.estimated_impact} impact)"):
            st.write(o.description)
            if o.action_items:
                st.write("**Actions:**")
                for a in o.action_items:
                    st.write(f"- {a}")


def render_rocm_report(report: ROCmReadinessReport):
    st.subheader("🖥️ ROCm / AMD Readiness")
    col1, col2, col3 = st.columns(3)
    col1.metric("Compatible", "Yes" if report.model_compatible else "No")
    col2.metric("Recommended GPU", report.gpu_recommendation)
    col3.metric("Quantization", report.quantization_suggestion or "N/A")
    if report.kernel_optimizations:
        st.write("**Kernels:** " + ", ".join(report.kernel_optimizations))
    if report.notes:
        st.write("**Notes:**")
        for n in report.notes:
            st.write(f"- {n}")


def render_final_report(report: FinalReport):
    st.subheader("📊 Final Report")
    col1, col2, col3 = st.columns(3)
    col1.metric("Incidents", len(report.incidents))
    col2.metric("Triage Results", len(report.triage_results))
    col3.metric("Overall Trust Score", f"{report.overall_trust_score:.2f}")

    st.download_button(
        label="Download Markdown Report",
        data=report.summary_md,
        file_name="rocm_agentops_report.md",
        mime="text/markdown",
    )

    json_bytes = report.model_dump_json(indent=2).encode("utf-8")
    st.download_button(
        label="Download JSON Report",
        data=json_bytes,
        file_name="rocm_agentops_report.json",
        mime="application/json",
    )
