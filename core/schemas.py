"""Pydantic schemas for ROCm AgentOps."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


class IncidentSeverity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class IncidentStatus(str, Enum):
    OPEN = "open"
    INVESTIGATING = "investigating"
    MITIGATED = "mitigated"
    MONITORING = "monitoring"


class Incident(BaseModel):
    id: str
    title: str
    description: str
    severity_hint: IncidentSeverity = IncidentSeverity.MEDIUM
    status: IncidentStatus = IncidentStatus.OPEN
    system: str = "unknown"
    location: str = "us-east-1"
    reported_at: datetime = Field(default_factory=utc_now)
    evidence: List[str] = Field(default_factory=list)
    affected_users: int = 0
    revenue_impact_usd: float = 0.0
    sla_minutes_remaining: int = 60
    source: str = "demo_dataset"


class RiskFlag(BaseModel):
    code: str
    label: str
    severity: str
    explanation: str


class TriageDecision(BaseModel):
    incident_id: str
    title: str
    system: str
    status: str
    severity_hint: str
    priority_score: float = 0.0
    confidence_score: float = 0.0
    trust_score: float = 0.0
    recommended_action: str = ""
    reasons: List[str] = Field(default_factory=list)
    risk_flags: List[RiskFlag] = Field(default_factory=list)
    human_review_required: bool = False


class BaselineDecision(BaseModel):
    incident_id: str
    title: str
    system: str
    severity_hint: str
    affected_users: int = 0
    baseline_score: float = 0.0
    baseline_rank: int = 0


class AgentTraceEvent(BaseModel):
    run_id: str
    timestamp: str
    agent_name: str
    step_name: str
    input_summary: str
    output_summary: str
    latency_ms: float = 0.0
    status: str = "success"
    risk_flags: List[str] = Field(default_factory=list)
    estimated_tokens: int = 0
    estimated_cost_usd: float = 0.0


class TriageResult(BaseModel):
    incident_id: str
    priority_rank: int = Field(..., ge=1, le=10)
    reasoning: str
    risk_flags: List[str] = Field(default_factory=list)
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    estimated_cost_usd: float = 0.0
    estimated_latency_ms: int = 0
    assigned_team: str = "sre"
    recommendations: List[str] = Field(default_factory=list)


class AgentStep(BaseModel):
    step_name: str
    agent_name: str
    input_summary: str
    output_summary: str
    started_at: datetime = Field(default_factory=utc_now)
    finished_at: Optional[datetime] = None
    latency_ms: int = 0
    status: str = "success"


class AgentTrace(BaseModel):
    trace_id: str
    workflow_name: str
    started_at: datetime = Field(default_factory=utc_now)
    finished_at: Optional[datetime] = None
    steps: List[AgentStep] = Field(default_factory=list)

    def add_step(self, step: AgentStep) -> None:
        self.steps.append(step)


class OptimizationRecommendation(BaseModel):
    category: str = ""
    title: str = ""
    description: str = ""
    recommendation: str = ""
    expected_benefit: str = ""
    complexity: str = ""
    estimated_impact: str = ""
    action_items: List[str] = Field(default_factory=list)
    rationale: str = ""


class ROCmReadinessReport(BaseModel):
    summary: str = ""
    gpu_relevant_steps: List[str] = Field(default_factory=list)
    rocm_optimizations: List[str] = Field(default_factory=list)
    batching_opportunities: List[str] = Field(default_factory=list)
    estimated_impact: str = ""
    limitations: List[str] = Field(default_factory=list)
    model_compatible: bool = True
    gpu_recommendation: str = "MI300X"
    kernel_optimizations: List[str] = Field(default_factory=list)
    quantization_suggestion: Optional[str] = None
    notes: List[str] = Field(default_factory=list)


class ModelRouteDecision(BaseModel):
    incident_id: str
    title: str
    system: str
    risk_tier: str
    selected_execution_mode: str
    recommended_model: str
    reason: str
    expected_latency_ms: float = 0.0
    expected_cost_usd: float = 0.0
    safety_notes: List[str] = Field(default_factory=list)
    owner_email: str = ""
    owner_name: str = ""
    policy_hits: List[str] = Field(default_factory=list)


class WorkflowStrategyResult(BaseModel):
    strategy_name: str
    description: str
    total_estimated_latency_ms: float = 0.0
    p95_latency_risk: str = ""
    estimated_cost_usd: float = 0.0
    expected_quality_score: float = 0.0
    risk_coverage_score: float = 0.0
    human_review_count: int = 0
    model_calls: int = 0
    deterministic_steps: int = 0
    recommended: bool = False
    benchmark_source: str = ""
    risks: List[str] = Field(default_factory=list)
    rationale: str = ""


class SLAMonitorResult(BaseModel):
    status: str
    summary_message: str = ""
    violations: List[str] = Field(default_factory=list)
    recommended_mitigation: List[str] = Field(default_factory=list)
    thresholds: Dict[str, float] = Field(default_factory=dict)


class PolicyRule(BaseModel):
    policy_id: str
    name: str
    description: str
    enforcement: str


class PolicyHit(BaseModel):
    policy_id: str
    policy_name: str
    enforcement: str
    description: str
    incident_id: Optional[str] = None


class PolicyComplianceSummary(BaseModel):
    compliance_status: str
    summary: str
    loaded_policies: List[PolicyRule] = Field(default_factory=list)
    triggered_policies: List[PolicyHit] = Field(default_factory=list)
    incident_policy_hits: Dict[str, List[str]] = Field(default_factory=dict)


class EscalationPacket(BaseModel):
    incident_id: str
    recipient_name: str
    recipient_email: str
    slack_channel: str
    subject: str
    markdown_body: str
    eml_content: str
    priority_score: float = 0.0
    trust_score: float = 0.0
    risk_flags: List[str] = Field(default_factory=list)
    recommended_action: str = ""
    sla_minutes_remaining: Optional[int] = None
    run_id: str = ""
    audit_id: str = ""
    benchmark_run_id: str = ""
    policy_hits: List[str] = Field(default_factory=list)


class AuditSeal(BaseModel):
    audit_id: str
    sha256: str
    generated_at: str
    included_fields: List[str] = Field(default_factory=list)
    explanation: str


class TelemetryCard(BaseModel):
    title: str
    markdown: str
    suggested_post_text: str = ""
    hashtags: List[str] = Field(default_factory=list)
    workflow_run_id: str = ""
    benchmark_run_id: str
    model: str
    success_rate: float = 0.0
    p50_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    tokens_per_second: float = 0.0


class HistoricalRoutingAnalytics(BaseModel):
    deterministic_only_pct: float = 0.0
    small_model_pct: float = 0.0
    large_model_pct: float = 0.0
    human_review_pct: float = 0.0
    estimated_cost_avoided_vs_all_large_model_usd: float = 0.0
    estimated_latency_avoided_vs_all_large_model_ms: float = 0.0
    summary: str = ""


class WarRoomPacketArtifact(BaseModel):
    file_name: str
    media_type: str = "application/zip"
    content: bytes = b""
    included_files: List[str] = Field(default_factory=list)
    description: str = ""


class AgentRunResult(BaseModel):
    run_id: str
    triage_results: List[TriageDecision] = Field(default_factory=list)
    baseline_results: List[BaselineDecision] = Field(default_factory=list)
    trace: List[AgentTraceEvent] = Field(default_factory=list)
    optimizations: List[OptimizationRecommendation] = Field(default_factory=list)
    rocm_report: Optional[ROCmReadinessReport] = None
    agent_review_markdown: str = ""
    comparison_markdown: str = ""
    final_report_markdown: str = ""
    llm_runtime_info: Dict[str, Any] = Field(default_factory=dict)
    command_center_summary: str = ""
    model_routes: List[ModelRouteDecision] = Field(default_factory=list)
    strategy_results: List[WorkflowStrategyResult] = Field(default_factory=list)
    recommended_strategy: Optional[WorkflowStrategyResult] = None
    sla_monitor_result: Optional[SLAMonitorResult] = None
    policy_compliance: Optional[PolicyComplianceSummary] = None
    historical_analytics: Optional[HistoricalRoutingAnalytics] = None
    escalation_packets: List[EscalationPacket] = Field(default_factory=list)
    audit_seal: Optional[AuditSeal] = None
    telemetry_card: Optional[TelemetryCard] = None
    war_room_packet: Optional[WarRoomPacketArtifact] = None


class FinalReport(BaseModel):
    report_id: str
    generated_at: datetime = Field(default_factory=utc_now)
    incidents: List[Incident] = Field(default_factory=list)
    triage_results: List[TriageResult] = Field(default_factory=list)
    trace: Optional[AgentTrace] = None
    optimizations: List[OptimizationRecommendation] = Field(default_factory=list)
    rocm_report: Optional[ROCmReadinessReport] = None
    overall_trust_score: float = Field(0.0, ge=0.0, le=1.0)
    summary_md: str = ""
