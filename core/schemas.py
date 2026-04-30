"""Pydantic schemas for ROCm AgentOps."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


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
    reported_at: datetime = Field(default_factory=datetime.utcnow)
    evidence: List[str] = Field(default_factory=list)
    affected_users: int = 0
    revenue_impact_usd: float = 0.0
    sla_minutes_remaining: int = 60


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
    started_at: datetime = Field(default_factory=datetime.utcnow)
    finished_at: Optional[datetime] = None
    latency_ms: int = 0
    status: str = "success"  # success, error, retry


class AgentTrace(BaseModel):
    trace_id: str
    workflow_name: str
    started_at: datetime = Field(default_factory=datetime.utcnow)
    finished_at: Optional[datetime] = None
    steps: List[AgentStep] = Field(default_factory=list)

    def add_step(self, step: AgentStep) -> None:
        self.steps.append(step)


class OptimizationRecommendation(BaseModel):
    category: str  # cost, latency, accuracy, trust
    title: str
    description: str
    estimated_impact: str  # high, medium, low
    action_items: List[str] = Field(default_factory=list)


class ROCmReadinessReport(BaseModel):
    model_compatible: bool = True
    gpu_recommendation: str = "MI300X"
    kernel_optimizations: List[str] = Field(default_factory=list)
    quantization_suggestion: Optional[str] = None
    notes: List[str] = Field(default_factory=list)


class FinalReport(BaseModel):
    report_id: str
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    incidents: List[Incident] = Field(default_factory=list)
    triage_results: List[TriageResult] = Field(default_factory=list)
    trace: Optional[AgentTrace] = None
    optimizations: List[OptimizationRecommendation] = Field(default_factory=list)
    rocm_report: Optional[ROCmReadinessReport] = None
    overall_trust_score: float = Field(0.0, ge=0.0, le=1.0)
    summary_md: str = ""
