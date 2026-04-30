"""Reusable Streamlit UI components."""

from typing import List, Optional

import pandas as pd
import plotly.express as px
import streamlit as st

from core.schemas import (
    AgentRunResult,
    AgentTrace,
    AgentTraceEvent,
    Incident,
    OptimizationRecommendation,
    ROCmReadinessReport,
    TriageDecision,
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


def render_triage_results(results: List[TriageDecision]):
    st.subheader("🚦 Triage Results")
    if not results:
        st.info("No triage results yet.")
        return

    rows = []
    for rank, r in enumerate(results, start=1):
        rows.append({
            "rank": rank,
            "incident_id": r.incident_id,
            "title": r.title,
            "system": r.system,
            "status": r.status,
            "severity_hint": r.severity_hint,
            "priority_score": r.priority_score,
            "confidence_score": r.confidence_score,
            "trust_score": r.trust_score,
            "human_review_required": r.human_review_required,
            "recommended_action": r.recommended_action,
        })
    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True)

    # Bar chart of priority scores
    fig = px.bar(
        df,
        x="incident_id",
        y="priority_score",
        color="severity_hint",
        title="Priority Score by Incident",
        labels={"priority_score": "Priority", "incident_id": "Incident"},
    )
    st.plotly_chart(fig, use_container_width=True)

    # Expandable details
    for r in results:
        with st.expander(f"{r.incident_id} — {r.title} (Priority: {r.priority_score})"):
            st.write(f"**Recommended Action:** {r.recommended_action}")
            st.write(f"**Human Review Required:** {'Yes' if r.human_review_required else 'No'}")
            if r.reasons:
                st.write("**Reasons:**")
                for reason in r.reasons:
                    st.write(f"- {reason}")
            if r.risk_flags:
                st.write("**Risk Flags:**")
                for f in r.risk_flags:
                    st.write(f"- **{f.label}** ({f.severity}): {f.explanation}")


def render_trace(trace: List[AgentTraceEvent]):
    st.subheader("🔍 Agent Trace Timeline")
    if not trace:
        st.info("No trace available.")
        return

    rows = []
    for evt in trace:
        rows.append({
            "Agent": evt.agent_name,
            "Step": evt.step_name,
            "Latency (ms)": evt.latency_ms,
            "Status": evt.status,
            "Input": evt.input_summary[:120],
            "Output": evt.output_summary[:120],
            "Risk Flags": ", ".join(evt.risk_flags) if evt.risk_flags else "—",
            "Est. Cost": f"${evt.estimated_cost_usd:.4f}",
        })
    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True)

    # Horizontal bar chart of latencies (numeric axis, not datetime)
    df["Task"] = df["Agent"] + " — " + df["Step"]
    fig = px.bar(
        df,
        x="Latency (ms)",
        y="Task",
        color="Status",
        orientation="h",
        title="Agent Step Latencies",
        labels={"Latency (ms)": "Latency (ms)", "Task": ""},
    )
    fig.update_layout(xaxis_type="linear")
    st.plotly_chart(fig, use_container_width=True)


def render_optimizations(opts: List[OptimizationRecommendation]):
    st.subheader("⚡ Optimization Recommendations")
    if not opts:
        st.info("No optimizations suggested.")
        return
    for o in opts:
        with st.expander(f"{o.title} ({o.category}, {o.estimated_impact} impact)"):
            if o.description:
                st.write(o.description)
            if o.recommendation:
                st.write(f"**Recommendation:** {o.recommendation}")
            if o.expected_benefit:
                st.write(f"**Expected Benefit:** {o.expected_benefit}")
            if o.complexity:
                st.write(f"**Complexity:** {o.complexity}")
            if o.action_items:
                st.write("**Actions:**")
                for a in o.action_items:
                    st.write(f"- {a}")


def render_rocm_report(report: Optional[ROCmReadinessReport]):
    st.subheader("🖥️ ROCm / AMD Readiness")
    if not report:
        st.info("No ROCm readiness report available.")
        return

    st.write(f"**Summary:** {report.summary}")
    st.write(f"**Estimated Impact:** {report.estimated_impact}")

    if report.gpu_relevant_steps:
        st.write(f"**GPU Relevant Steps:** {', '.join(report.gpu_relevant_steps)}")

    if report.rocm_optimizations:
        st.write("**ROCm Optimizations:**")
        for opt in report.rocm_optimizations:
            st.write(f"- {opt}")

    if report.batching_opportunities:
        st.write("**Batching Opportunities:**")
        for b in report.batching_opportunities:
            st.write(f"- {b}")

    if report.limitations:
        st.write("**Limitations:**")
        for lim in report.limitations:
            st.write(f"- {lim}")

    # Legacy compatibility metrics
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


def render_final_report(report: AgentRunResult):
    st.subheader("📊 Final Report")
    col1, col2, col3 = st.columns(3)
    col1.metric("Incidents", len(report.triage_results))
    col2.metric("Trace Events", len(report.trace))
    col3.metric("Optimizations", len(report.optimizations))

    st.markdown(report.final_report_markdown)

    st.download_button(
        label="Download Markdown Report",
        data=report.final_report_markdown,
        file_name="rocm_agentops_report.md",
        mime="text/markdown",
    )
