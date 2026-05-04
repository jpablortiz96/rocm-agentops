"""ROCm AgentOps — Streamlit entrypoint."""

import json
from pathlib import Path

import streamlit as st

from core.benchmarking import load_benchmark_results
from core.config import config
from core.schemas import Incident
from ui.components import (
    render_agent_review,
    render_amd_live_evidence,
    render_baseline_comparison,
    render_final_report,
    render_header,
    render_incidents,
    render_optimizations,
    render_rocm_report,
    render_sidebar,
    render_trace,
    render_triage_results,
)
from workflows.incident_triage_workflow import IncidentTriageWorkflow


def load_sample_incidents() -> list[Incident]:
    data_path = Path("data/sample_incidents.json")
    if not data_path.exists():
        st.error("Sample incidents file not found.")
        return []
    with open(data_path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    return [Incident.model_validate(r) for r in raw]


def main():
    render_header()
    settings = render_sidebar()

    # Update LLM config dynamically from sidebar
    from core.llm_client import LLMClient

    llm_client = LLMClient(
        api_key=settings["api_key"] or config.LLM_API_KEY,
        base_url=settings["base_url"],
        model=settings["model"],
        mock=settings["mock_mode"],
    )

    st.subheader("🚀 Incident Triage Demo")
    st.write(
        "Load sample incidents and run the AgentOps triage workflow. "
        "Toggle Mock LLM Mode in the sidebar to run without API keys."
    )

    incidents = load_sample_incidents()

    if incidents:
        with st.expander("🔎 Filters", expanded=True):
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                system_opts = sorted({i.system for i in incidents})
                system_filter = st.multiselect("System", system_opts, default=[])
            with col2:
                status_opts = sorted({i.status.value for i in incidents})
                status_filter = st.multiselect("Status", status_opts, default=[])
            with col3:
                severity_opts = sorted({i.severity_hint.value for i in incidents})
                severity_filter = st.multiselect("Severity", severity_opts, default=[])
            with col4:
                location_opts = sorted({i.location for i in incidents})
                location_filter = st.multiselect("Location", location_opts, default=[])

        filtered = incidents
        if system_filter:
            filtered = [i for i in filtered if i.system in system_filter]
        if status_filter:
            filtered = [i for i in filtered if i.status.value in status_filter]
        if severity_filter:
            filtered = [i for i in filtered if i.severity_hint.value in severity_filter]
        if location_filter:
            filtered = [i for i in filtered if i.location in location_filter]
    else:
        filtered = incidents

    render_incidents(filtered)

    if not incidents:
        st.stop()

    if st.button("Run Triage Workflow", type="primary"):
        with st.spinner("Running agentic workflow..."):
            workflow = IncidentTriageWorkflow(llm_client=llm_client)
            report = workflow.run(filtered)

        st.success("Workflow complete!")

        # Load AMD benchmark results independently of workflow run
        benchmark_summary = load_benchmark_results("data/amd_benchmark_results.json")

        # Tab order: Triage, Agent Review, Trace, Optimizations, ROCm Readiness, AMD Live Evidence, Final Report
        tab_triage, tab_agent_review, tab_trace, tab_opt, tab_rocm, tab_amd, tab_report = st.tabs(
            ["Triage", "Agent Review", "Trace", "Optimizations", "ROCm Readiness", "AMD Live Evidence", "Final Report"]
        )

        with tab_triage:
            render_baseline_comparison(report.baseline_results, report.triage_results)
            render_triage_results(report.triage_results)

        with tab_agent_review:
            render_agent_review(report.agent_review_markdown, report.llm_runtime_info)

        with tab_trace:
            if report.trace:
                render_trace(report.trace)

        with tab_opt:
            render_optimizations(report.optimizations)

        with tab_rocm:
            if report.rocm_report:
                render_rocm_report(report.rocm_report)

        with tab_amd:
            render_amd_live_evidence(benchmark_summary)

        with tab_report:
            render_final_report(report)


if __name__ == "__main__":
    main()
