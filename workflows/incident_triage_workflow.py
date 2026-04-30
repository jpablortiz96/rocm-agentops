"""Incident Triage Workflow: orchestrates agents end-to-end."""

from typing import List

from agents.critic_agent import CriticAgent
from agents.optimizer_agent import OptimizerAgent
from agents.planner_agent import PlannerAgent
from agents.reporter_agent import ReporterAgent
from agents.rocm_advisor_agent import ROCmAdvisorAgent
from agents.triage_agent import TriageAgent
from core.llm_client import LLMClient, llm
from core.schemas import FinalReport, Incident
from core.tracing import TraceBuilder


class IncidentTriageWorkflow:
    """End-to-end workflow for incident triage."""

    def __init__(self, llm_client: LLMClient = llm):
        self.planner = PlannerAgent(llm_client)
        self.triage = TriageAgent(llm_client)
        self.critic = CriticAgent(llm_client)
        self.optimizer = OptimizerAgent(llm_client)
        self.rocm_advisor = ROCmAdvisorAgent(llm_client)
        self.reporter = ReporterAgent()

    def run(self, incidents: List[Incident]) -> FinalReport:
        """Execute the full workflow and return a FinalReport."""
        trace_builder = TraceBuilder(workflow_name="incident_triage")

        # 1. Plan
        plan = self.planner.plan(incidents, trace_builder)
        incident_map = {i.id: i for i in incidents}

        # 2. Triage + Critic per incident
        triage_results = []
        for rank, inc_id in enumerate(plan, start=1):
            incident = incident_map[inc_id]
            result = self.triage.triage(incident, rank, trace_builder)
            result = self.critic.review(incident, result, trace_builder)
            triage_results.append(result)

        # 3. Optimize
        trace = trace_builder.trace
        optimizations = self.optimizer.optimize(triage_results, trace, trace_builder)

        # 4. ROCm readiness
        rocm_report = self.rocm_advisor.advise(
            model_name=self._detect_model(),
            trace_builder=trace_builder,
        )

        # 5. Report
        final = self.reporter.build_report(
            incidents=incidents,
            triage_results=triage_results,
            trace=trace_builder.finalize(),
            optimizations=optimizations,
            rocm_report=rocm_report,
            trace_builder=trace_builder,
        )
        return final

    def _detect_model(self) -> str:
        """Simple model name detection for demo purposes."""
        return llm.model
