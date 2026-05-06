"""ROCm AgentOps Streamlit entrypoint."""

from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

from core.benchmarking import load_preferred_benchmark_results
from core.config import config
from core.schemas import AgentRunResult, Incident
from live.live_incident_engine import LiveIncidentRun, generate_live_incidents
from ui.components import (
    render_agent_review,
    render_amd_live_evidence,
    render_baseline_comparison,
    render_command_center,
    render_final_report,
    render_header,
    render_incident_source_controls,
    render_incident_source_panel,
    render_incidents,
    render_optimizations,
    render_overview,
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

    raw = json.loads(data_path.read_text(encoding="utf-8"))
    return [Incident.model_validate(record) for record in raw]


def build_incident_signature(incidents: list[Incident]) -> tuple[str, ...]:
    return tuple(f"{incident.id}:{incident.source}" for incident in incidents)


def load_live_incidents(
    *,
    base_url: str,
    model: str,
    api_key: str,
    mock_mode: bool,
    enable_live_endpoint_probe: bool,
    thresholds: dict[str, float],
) -> LiveIncidentRun:
    try:
        return generate_live_incidents(
            base_url=base_url,
            model=model,
            api_key=api_key,
            mock_mode=mock_mode,
            enable_live_endpoint_probe=enable_live_endpoint_probe,
            thresholds=thresholds,
        )
    except Exception as exc:  # noqa: BLE001
        return LiveIncidentRun(
            incidents=[],
            signal_summary={
                "live_evidence_enabled": True,
                "endpoint_health": "collector_error",
                "endpoint_available": False,
                "benchmark_available": False,
                "gpu_telemetry_available": False,
                "logs_available": False,
                "live_incidents_generated": 0,
                "findings": [],
                "no_incident_reason": "Live signal collection did not complete successfully.",
                "thresholds": thresholds,
                "details": {"error": str(exc)},
            },
        )


def main() -> None:
    render_header()
    settings = render_sidebar()
    benchmark_summary = load_preferred_benchmark_results()

    from core.llm_client import LLMClient

    llm_client = LLMClient(
        api_key=settings["api_key"] or config.LLM_API_KEY,
        base_url=settings["base_url"],
        model=settings["model"],
        mock=settings["mock_mode"],
    )

    st.markdown("### Workflow Intake")
    st.write(
        "Load incident records and compile them into a deterministic, benchmark-aware execution plan. "
        "Mock mode remains available for runtime resilience; live mode can connect to your verified AMD/vLLM endpoint."
    )
    if benchmark_summary and benchmark_summary.artifact_origin == "example":
        st.info(
            "Using the bundled example AMD benchmark artifact. Connect an external AMD/vLLM endpoint or refresh the benchmark locally to replace it with live evidence."
        )

    source_options = ["Demo Dataset", "AMD Live Signals", "Hybrid"]
    source_mode = st.session_state.get("incident_source_mode", config.INCIDENT_SOURCE_MODE)
    if source_mode not in source_options:
        source_mode = "Demo Dataset"

    threshold_defaults = {
        "p95_latency_sla_ms": float(st.session_state.get("threshold_p95_latency_sla_ms", config.LIVE_P95_THRESHOLD_MS)),
        "warning_threshold_pct": float(st.session_state.get("threshold_warning_threshold_pct", 0.90)),
        "minimum_success_rate": float(st.session_state.get("threshold_minimum_success_rate", 0.95)),
        "max_failed_requests": int(st.session_state.get("threshold_max_failed_requests", 0)),
    }
    selected_source_mode, enable_live_endpoint_probe, live_thresholds = render_incident_source_controls(
        source_mode=source_mode,
        source_options=source_options,
        threshold_defaults=threshold_defaults,
    )
    if selected_source_mode != source_mode:
        st.session_state["incident_source_mode"] = selected_source_mode
        st.rerun()

    live_run = LiveIncidentRun(incidents=[], signal_summary={})
    if selected_source_mode != "Demo Dataset" or enable_live_endpoint_probe:
        live_run = load_live_incidents(
            base_url=settings["base_url"],
            model=settings["model"],
            api_key=settings["api_key"],
            mock_mode=settings["mock_mode"],
            enable_live_endpoint_probe=enable_live_endpoint_probe,
            thresholds=live_thresholds,
        )

    if selected_source_mode != "Demo Dataset" or enable_live_endpoint_probe:
        render_incident_source_panel(signal_summary=live_run.signal_summary)

    demo_incidents = load_sample_incidents()
    if selected_source_mode == "AMD Live Signals":
        incidents = live_run.incidents
    elif selected_source_mode == "Hybrid":
        incidents = [*demo_incidents, *live_run.incidents]
    else:
        incidents = demo_incidents

    filtered = incidents

    if incidents:
        with st.expander("Filters", expanded=True):
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                system_opts = sorted({incident.system for incident in incidents})
                system_filter = st.multiselect("System", system_opts, default=[])
            with col2:
                status_opts = sorted({incident.status.value for incident in incidents})
                status_filter = st.multiselect("Status", status_opts, default=[])
            with col3:
                severity_opts = sorted({incident.severity_hint.value for incident in incidents})
                severity_filter = st.multiselect("Severity", severity_opts, default=[])
            with col4:
                location_opts = sorted({incident.location for incident in incidents})
                location_filter = st.multiselect("Location", location_opts, default=[])

        if system_filter:
            filtered = [incident for incident in filtered if incident.system in system_filter]
        if status_filter:
            filtered = [incident for incident in filtered if incident.status.value in status_filter]
        if severity_filter:
            filtered = [incident for incident in filtered if incident.severity_hint.value in severity_filter]
        if location_filter:
            filtered = [incident for incident in filtered if incident.location in location_filter]

    render_incidents(filtered)

    if not incidents:
        if selected_source_mode == "AMD Live Signals":
            st.info(
                "No live incidents generated because all signals are within thresholds. "
                "Adjust the SLA threshold or use Hybrid mode to combine live workload evidence with business incident templates."
            )
        else:
            st.info(
                "No incidents are available for the selected source mode. "
                "Demo Dataset always loads the business incident template set; AMD Live Signals depends on benchmark, endpoint, log, or telemetry evidence."
            )
        _render_preflight_panel(benchmark_summary)
        st.stop()

    current_signature = build_incident_signature(filtered)
    latest_signature = st.session_state.get("latest_report_incident_signature")
    latest_source_mode = st.session_state.get("latest_report_source_mode")
    latest_probe_enabled = st.session_state.get("latest_report_live_probe_enabled")
    latest_thresholds = st.session_state.get("latest_report_live_thresholds")
    latest_report: AgentRunResult | None = st.session_state.get("latest_report")

    if latest_report and (
        latest_signature != current_signature
        or latest_source_mode != selected_source_mode
        or latest_probe_enabled != enable_live_endpoint_probe
        or latest_thresholds != live_thresholds
    ):
        st.warning(
            "The current report reflects a previous incident source or filter selection. "
            "Run the workflow again to refresh the Command Center and final report."
        )

    if st.button("Run Triage Workflow", type="primary"):
        with st.spinner("Compiling workflow and assembling operational artifacts..."):
            report = IncidentTriageWorkflow(llm_client=llm_client).run(filtered)
        st.session_state["latest_report"] = report
        st.session_state["latest_report_incident_signature"] = current_signature
        st.session_state["latest_report_source_mode"] = selected_source_mode
        st.session_state["latest_report_live_probe_enabled"] = enable_live_endpoint_probe
        st.session_state["latest_report_live_thresholds"] = live_thresholds
        st.success("Workflow complete.")

    report = st.session_state.get("latest_report")
    if not report:
        _render_preflight_panel(benchmark_summary)
        return

    (
        tab_overview,
        tab_triage,
        tab_agent_review,
        tab_command_center,
        tab_trace,
        tab_opt,
        tab_rocm,
        tab_amd,
        tab_report,
    ) = st.tabs(
        [
            "Overview",
            "Triage",
            "Agent Review",
            "Command Center",
            "Trace",
            "Optimizations",
            "ROCm Readiness",
            "AMD Evidence",
            "Final Report",
        ]
    )

    with tab_overview:
        render_overview(report, benchmark_summary, settings["report_mode"])

    with tab_triage:
        render_baseline_comparison(report.baseline_results, report.triage_results)
        render_triage_results(report.triage_results)

    with tab_agent_review:
        render_agent_review(report.agent_review_markdown, report.llm_runtime_info)

    with tab_command_center:
        render_command_center(report)

    with tab_trace:
        render_trace(report.trace)

    with tab_opt:
        render_optimizations(report.optimizations)

    with tab_rocm:
        render_rocm_report(report.rocm_report)

    with tab_amd:
        render_amd_live_evidence(benchmark_summary)

    with tab_report:
        render_final_report(report, settings["report_mode"], benchmark_summary)


def _render_preflight_panel(benchmark_summary) -> None:
    with st.container(border=True):
        st.markdown("### Platform Status")
        col1, col2, col3 = st.columns(3)
        benchmark_label = "Pending"
        if benchmark_summary and benchmark_summary.successful_requests > 0:
            benchmark_label = (
                "Example Artifact"
                if benchmark_summary.artifact_origin == "example"
                else "Verified"
            )
        col1.metric("AMD Benchmark", benchmark_label)
        col2.metric("Benchmark Success", f"{benchmark_summary.successful_requests}/{benchmark_summary.total_requests}" if benchmark_summary else "N/A")
        col3.metric("p95 Latency", f"{benchmark_summary.p95_latency_ms:.0f} ms" if benchmark_summary else "N/A")
        st.caption("Run the workflow to unlock the premium Overview, Command Center, and War Room Packet artifacts.")


if __name__ == "__main__":
    main()
