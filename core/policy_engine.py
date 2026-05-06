"""Policy-as-code guardrails for ROCm AgentOps."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, Optional

from core.benchmark_schemas import AmdBenchmarkSummary
from core.schemas import (
    ModelRouteDecision,
    PolicyComplianceSummary,
    PolicyHit,
    PolicyRule,
    SLAMonitorResult,
    TriageDecision,
)

POLICIES_PATH = "data/policies.json"


def load_policy_configuration(path: str = POLICIES_PATH) -> dict[str, object]:
    """Load the static policy bundle from disk."""
    policy_path = Path(path)
    if not policy_path.exists():
        return {"rules": [], "thresholds": {}}

    raw = json.loads(policy_path.read_text(encoding="utf-8"))
    rules = [PolicyRule.model_validate(rule) for rule in raw.get("rules", [])]
    thresholds = {
        key: float(value) for key, value in raw.get("thresholds", {}).items()
    }
    return {"rules": rules, "thresholds": thresholds}


def evaluate_policy_compliance(
    triage_decisions: Iterable[TriageDecision],
    model_routes: Iterable[ModelRouteDecision],
    sla_monitor_result: Optional[SLAMonitorResult],
    *,
    benchmark_summary: Optional[AmdBenchmarkSummary] = None,
    policy_configuration: Optional[dict[str, object]] = None,
) -> PolicyComplianceSummary:
    """Evaluate which guardrail policies fired and whether routing complied."""
    config = policy_configuration or load_policy_configuration()
    rules = list(config.get("rules", []))
    thresholds = dict(config.get("thresholds", {}))
    trust_threshold = float(thresholds.get("minimum_trust_score_autonomous_action", 60.0))
    p95_threshold = float(thresholds.get("p95_latency_ms", 2500.0))

    decisions = list(triage_decisions)
    route_by_incident = {route.incident_id: route for route in model_routes}
    triggered_policies: list[PolicyHit] = []
    incident_policy_hits: dict[str, list[str]] = {}
    compliance_ok = True

    for decision in decisions:
        route = route_by_incident.get(decision.incident_id)
        flag_codes = {flag.code for flag in decision.risk_flags}

        if decision.system == "security" and "SECURITY_WITHOUT_EVIDENCE" in flag_codes:
            _register_policy_hit(
                triggered_policies,
                incident_policy_hits,
                _find_rule(rules, "POL-001"),
                incident_id=decision.incident_id,
            )
            if not route or route.selected_execution_mode != "human_review":
                compliance_ok = False

        if decision.priority_score >= 85:
            _register_policy_hit(
                triggered_policies,
                incident_policy_hits,
                _find_rule(rules, "POL-002"),
                incident_id=decision.incident_id,
            )
            if decision.recommended_action != "Page on-call immediately":
                compliance_ok = False

        if "HALLUCINATION_RISK" in flag_codes:
            _register_policy_hit(
                triggered_policies,
                incident_policy_hits,
                _find_rule(rules, "POL-003"),
                incident_id=decision.incident_id,
            )
            if not route or route.selected_execution_mode != "human_review":
                compliance_ok = False

        if decision.trust_score < trust_threshold:
            _register_policy_hit(
                triggered_policies,
                incident_policy_hits,
                _find_rule(rules, "POL-005"),
                incident_id=decision.incident_id,
            )
            if not route or route.selected_execution_mode != "human_review":
                compliance_ok = False

    if benchmark_summary is not None and benchmark_summary.p95_latency_ms >= p95_threshold * 0.9:
        _register_policy_hit(
            triggered_policies,
            incident_policy_hits,
            _find_rule(rules, "POL-004"),
            incident_id=None,
            override_description=(
                f"Benchmark p95 is {benchmark_summary.p95_latency_ms:.2f} ms against the {p95_threshold:.0f} ms policy threshold."
            ),
        )

    if sla_monitor_result and sla_monitor_result.status in {"WARN", "FAIL", "PASS_WITH_WARNING"}:
        compliance_ok = compliance_ok and sla_monitor_result.status != "FAIL"

    summary = (
        f"Loaded {len(rules)} guardrail policies and triggered {len(triggered_policies)} policy hit(s) "
        f"across {len([k for k in incident_policy_hits if k != 'global'])} incident routing decisions."
    )

    return PolicyComplianceSummary(
        compliance_status="COMPLIANT" if compliance_ok else "REVIEW_REQUIRED",
        summary=summary,
        loaded_policies=rules,
        triggered_policies=triggered_policies,
        incident_policy_hits=incident_policy_hits,
    )


def apply_policy_hits_to_routes(
    model_routes: Iterable[ModelRouteDecision],
    policy_compliance: PolicyComplianceSummary,
) -> list[ModelRouteDecision]:
    """Annotate route decisions with the policies that influenced them."""
    incident_hits = policy_compliance.incident_policy_hits
    routes = list(model_routes)
    for route in routes:
        route.policy_hits = incident_hits.get(route.incident_id, [])
        if route.policy_hits:
            route.safety_notes.append(f"Policy hits: {', '.join(route.policy_hits)}")
    return routes


def _find_rule(rules: list[PolicyRule], policy_id: str) -> PolicyRule:
    for rule in rules:
        if rule.policy_id == policy_id:
            return rule
    return PolicyRule(
        policy_id=policy_id,
        name=policy_id,
        description="Policy rule not found in configuration.",
        enforcement="review",
    )


def _register_policy_hit(
    triggered_policies: list[PolicyHit],
    incident_policy_hits: dict[str, list[str]],
    rule: PolicyRule,
    *,
    incident_id: Optional[str],
    override_description: Optional[str] = None,
) -> None:
    triggered_policies.append(
        PolicyHit(
            policy_id=rule.policy_id,
            policy_name=rule.name,
            enforcement=rule.enforcement,
            description=override_description or rule.description,
            incident_id=incident_id,
        )
    )
    incident_key = incident_id or "global"
    incident_policy_hits.setdefault(incident_key, []).append(rule.policy_id)
