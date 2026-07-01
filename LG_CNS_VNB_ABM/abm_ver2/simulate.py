#!/usr/bin/env python3
"""시뮬레이션 실행 → JSON 데이터 출력"""
import json
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
from model import LGCNSDevModel
from tasks import TASK_DOMAINS


ROLE_STAFFING_COST = {
    "junior": 1.0,
    "middle": 1.6,
    "senior": 2.5,
}


def _staffing_metrics(developers: list, completed_task_count: int) -> dict:
    staffing_cost = sum(
        ROLE_STAFFING_COST.get(getattr(dev, "role", None), 1.6)
        for dev in developers
    )
    total_prs = sum(getattr(dev, "prs_created", 0) for dev in developers)
    return {
        "staffing_cost": round(staffing_cost, 3),
        "completed_tasks_per_cost": round(
            completed_task_count / staffing_cost if staffing_cost else 0.0,
            3,
        ),
        "PRs_per_cost": round(
            total_prs / staffing_cost if staffing_cost else 0.0,
            3,
        ),
    }


def _domain_knowledge_metrics(active_developers: list) -> dict:
    values = []
    for dev in active_developers:
        values.extend(dev.domain_knowledge.get(domain, 0.0) for domain in TASK_DOMAINS)

    covered_domains = sum(
        1 for domain in TASK_DOMAINS
        if any(dev.domain_knowledge.get(domain, 0.0) >= 0.6 for dev in active_developers)
    )

    if not values:
        return {
            "avg_team_domain_knowledge": 0.0,
            "min_team_domain_knowledge": 0.0,
            "domain_coverage": 0.0,
        }

    return {
        "avg_team_domain_knowledge": round(sum(values) / len(values), 2),
        "min_team_domain_knowledge": round(min(values), 2),
        "domain_coverage": round(covered_domains / max(len(TASK_DOMAINS), 1), 2),
    }


def _role_metrics(active_developers: list) -> dict:
    juniors = [d for d in active_developers if getattr(d, "role", None) == "junior"]
    middles = [d for d in active_developers if getattr(d, "role", None) == "middle"]
    seniors = [d for d in active_developers if getattr(d, "role", None) == "senior"]

    return {
        "junior_count": len(juniors),
        "middle_count": len(middles),
        "senior_count": len(seniors),
        "junior_avg_knowledge": round(
            sum(d.knowledge for d in juniors) / max(len(juniors), 1),
            2,
        ),
        "senior_mentoring_load": round(sum(d.mentoring_load for d in seniors), 2),
        "senior_mentoring_load_per_senior": round(
            sum(d.mentoring_load for d in seniors) / max(len(seniors), 1),
            3,
        ),
        "junior_help_requests": sum(d.help_requests_made for d in juniors),
    }


def _interaction_metrics(model, active_developers: list) -> dict:
    events = getattr(model, "interaction_events", [])
    active_ids = {dev.unique_id for dev in active_developers}
    senior_ids = {
        dev.unique_id
        for dev in active_developers
        if getattr(dev, "role", None) == "senior"
    }

    help_edges = {
        (event.get("source_id"), event.get("target_id"))
        for event in events
        if event.get("event_type") in {
            "help_request",
            "help_success",
            "help_failed",
            "mentoring",
        } and
        event.get("source_id") in active_ids and
        event.get("target_id") in active_ids and
        event.get("source_id") != event.get("target_id")
    }
    active_count = len(active_developers)
    possible_help_edges = active_count * max(active_count - 1, 0)
    help_network_density = (
        len(help_edges) / possible_help_edges
        if possible_help_edges else 0.0
    )

    senior_bottleneck_event_types = {
        "help_request",
        "help_success",
        "help_failed",
        "mentoring",
        "review_assignment",
        "incident_assignment",
        "incident_interrupt",
        "incident_interruption",
    }
    senior_target_events = [
        event for event in events
        if event.get("event_type") in senior_bottleneck_event_types and
        event.get("target_id") in active_ids
    ]
    senior_bottleneck_index = (
        sum(1 for event in senior_target_events if event.get("target_id") in senior_ids) /
        len(senior_target_events)
        if senior_target_events else 0.0
    )
    senior_target_event_count = sum(
        1 for event in senior_target_events
        if event.get("target_id") in senior_ids
    )
    help_request_count = sum(
        1 for event in events
        if event.get("event_type") == "help_request"
    )
    help_success_count = sum(
        1 for event in events
        if event.get("event_type") == "help_success"
    )
    help_resolution_rate = (
        help_success_count / help_request_count
        if help_request_count else 0.0
    )
    review_assignment_count = sum(
        1 for event in events
        if event.get("event_type") == "review_assignment"
    )
    senior_review_assignment_count = sum(
        1 for event in events
        if event.get("event_type") == "review_assignment" and
        event.get("target_id") in senior_ids
    )
    review_assignments_by_reviewer = {}
    for event in events:
        if event.get("event_type") != "review_assignment":
            continue
        reviewer_id = event.get("target_id")
        if reviewer_id is None:
            continue
        review_assignments_by_reviewer[reviewer_id] = (
            review_assignments_by_reviewer.get(reviewer_id, 0) + 1
        )
    review_concentration_index = (
        max(review_assignments_by_reviewer.values()) / review_assignment_count
        if review_assignment_count else 0.0
    )
    incident_interrupt_count = sum(
        1 for event in events
        if event.get("event_type") in {"incident_interrupt", "incident_interruption"}
    )
    pm_intervention_count = sum(
        1 for event in events
        if event.get("event_type") == "pm_intervention"
    )
    senior_count = len(senior_ids)
    target_counts = {dev_id: 0 for dev_id in senior_ids}
    for event in senior_target_events:
        target_id = event.get("target_id")
        if target_id in target_counts:
            target_counts[target_id] += 1
    avg_target_events = (
        len(senior_target_events) / max(active_count, 1)
        if senior_target_events else 0.0
    )
    senior_overload_count = 0
    for dev in active_developers:
        if getattr(dev, "role", None) != "senior":
            continue
        interaction_load = target_counts.get(dev.unique_id, 0)
        if (
            dev.energy < getattr(dev, "burnout_threshold", 0) * 1.35 or
            dev.mentoring_load >= 4.0 or
            interaction_load > max(3.0, avg_target_events * 1.5)
        ):
            senior_overload_count += 1

    return {
        "interaction_event_count": len(events),
        "interaction_load": round(
            len(events) / max(active_count, 1) / max(getattr(model, "total_steps", 0), 1),
            4,
        ),
        "help_request_count": help_request_count,
        "help_success_count": help_success_count,
        "help_resolution_rate": round(help_resolution_rate, 3),
        "help_network_density": round(help_network_density, 3),
        "senior_bottleneck_index": round(senior_bottleneck_index, 3),
        "review_assignment_count": review_assignment_count,
        "review_concentration_index": round(review_concentration_index, 3),
        "senior_review_load_per_senior": round(
            senior_review_assignment_count / max(senior_count, 1),
            3,
        ),
        "senior_interaction_load_per_senior": round(
            senior_target_event_count / max(senior_count, 1),
            3,
        ),
        "senior_overload_risk": round(
            senior_overload_count / max(senior_count, 1),
            3,
        ),
        "incident_interrupt_count": incident_interrupt_count,
        "incident_interruptions": incident_interrupt_count,
        "pm_intervention_count": pm_intervention_count,
    }


def run_simulation(params: dict) -> dict:
    include_interaction_events = bool(params.get("include_interaction_events", False))
    model_param_names = [
        "num_developers",
        "num_sprints",
        "project_type",
        "meeting_load",
        "review_strictness",
        "codebase_stability",
        "collaboration_tendency",
        "requirement_clarity",
        "knowledge_decay_rate",
        "sprint_backlog_size",
        "complexity_bias",
        "task_complexity_distribution",
        "domain_distribution",
        "task_type_distribution",
        "incident_probability_multiplier",
        "requirement_volatility",
        "quality_gate_cost_multiplier",
        "quality_gate_defect_multiplier",
        "seed",
        "distribution_overrides",
        "team_composition",
        "mentoring_intensity",
        "pm_profile",
        "allocation_skill",
        "bottleneck_detection",
        "requirement_coordination",
        "scope_control",
        "pm_intervention_capacity",
    ]
    model_params = {
        name: params[name]
        for name in model_param_names
        if name in params
    }
    m = LGCNSDevModel(**model_params)

    snapshots = []
    for _ in range(m.total_steps):
        m.step()
        active = [d for d in m.developers if not d.attrited]
        snapshot = {
            "step": m.current_step,
            "sprint": m.current_sprint,
            "agents": [{
                "id": d.unique_id,
                "skill": d.skill_level,
                "role": getattr(d, "role", None),
                "project_experience": round(d.project_experience, 2),
                "client_domain_experience": round(d.client_domain_experience, 2),
                "prior_collaboration_score": round(d.prior_collaboration_score, 2),
                "review_capacity": round(d.review_capacity, 2),
                "mentoring_capacity": round(d.mentoring_capacity, 2),
                "energy": round(d.energy, 1),
                "motivation": round(d.motivation, 1),
                "knowledge": round(d.knowledge, 1),
                "state": d.state,
                "attrited": d.attrited,
                "prs": d.prs_created,
                "flow_streak": d.flow_streak,
                "is_pl": False,
            } for d in m.developers] + [{
                "id": pl.unique_id,
                "skill": 3.0,
                "energy": round(pl.energy, 1),
                "motivation": round(pl.motivation, 1),
                "knowledge": 80.0,
                "state": pl.state,
                "attrited": False,
                "prs": 0,
                "flow_streak": 0,
                "is_pl": True,
            } for pl in m.pls],
            "metrics": {
                "avg_energy": round(sum(d.energy for d in active) / max(len(active), 1), 1),
                "avg_motivation": round(sum(d.motivation for d in active) / max(len(active), 1), 1),
                "avg_knowledge": round(sum(d.knowledge for d in active) / max(len(active), 1), 1),
                "total_prs": sum(d.prs_created for d in active),
                "deployments": m.metrics["deployments"],
                "incidents": m.metrics["failed_deployments"],
                "active_devs": len(active),
            },
        }
        snapshots.append(snapshot)

    active = [d for d in m.developers if not d.attrited]
    domain_metrics = _domain_knowledge_metrics(active)
    role_metrics = _role_metrics(active)
    interaction_metrics = _interaction_metrics(m, active)
    help_requests_total = m.metrics["help_requests_total"]
    help_requests_resolved = m.metrics["help_requests_resolved"]
    allocation_count = m.metrics["allocation_assignment_count"]
    rework_count = m.metrics["rework_count"]
    reviewed_tasks = m.metrics["reviewed_tasks"]
    completed_task_count = len(m.completed_tasks)
    completed_rework_total = sum(
        getattr(task, "rework_count", 0)
        for task in m.completed_tasks
    )
    staffing_metrics = _staffing_metrics(m.developers, completed_task_count)
    internal_metrics = {
        "avg_energy": round(sum(d.energy for d in active) / max(len(active), 1), 2),
        "avg_motivation": round(sum(d.motivation for d in active) / max(len(active), 1), 2),
        "min_energy": round(min((d.energy for d in active), default=0), 2),
        "avg_knowledge": round(sum(d.knowledge for d in active) / max(len(active), 1), 2),
        "avg_team_domain_knowledge": domain_metrics["avg_team_domain_knowledge"],
        "min_team_domain_knowledge": domain_metrics["min_team_domain_knowledge"],
        "domain_coverage": domain_metrics["domain_coverage"],
        "help_requests_total": help_requests_total,
        "help_requests_resolved": help_requests_resolved,
        "help_request_resolution_rate": round(
            help_requests_resolved / help_requests_total
            if help_requests_total else 0.0,
            2,
        ),
        "mentoring_load_total": round(m.metrics["mentoring_load_total"], 2),
        "avg_knowledge_gain_from_help": round(
            m.metrics["knowledge_gained_from_help_total"] / max(len(active), 1),
            4,
        ),
        "helper_interruptions": m.metrics["helper_interruptions"],
        "staffing_cost": staffing_metrics["staffing_cost"],
        "completed_tasks_per_cost": staffing_metrics["completed_tasks_per_cost"],
        "PRs_per_cost": staffing_metrics["PRs_per_cost"],
        "interaction_event_count": interaction_metrics["interaction_event_count"],
        "interaction_load": interaction_metrics["interaction_load"],
        "help_request_count": interaction_metrics["help_request_count"],
        "help_success_count": interaction_metrics["help_success_count"],
        "help_resolution_rate": interaction_metrics["help_resolution_rate"],
        "help_network_density": interaction_metrics["help_network_density"],
        "senior_bottleneck_index": interaction_metrics["senior_bottleneck_index"],
        "review_assignment_count": interaction_metrics["review_assignment_count"],
        "review_concentration_index": interaction_metrics["review_concentration_index"],
        "senior_review_load_per_senior": interaction_metrics["senior_review_load_per_senior"],
        "senior_interaction_load_per_senior": interaction_metrics["senior_interaction_load_per_senior"],
        "senior_overload_risk": interaction_metrics["senior_overload_risk"],
        "incident_interrupt_count": interaction_metrics["incident_interrupt_count"],
        "incident_interruptions": interaction_metrics["incident_interruptions"],
        "pm_intervention_count": interaction_metrics["pm_intervention_count"],
        "pm_leverage_index": round(
            completed_task_count / max(1, interaction_metrics["pm_intervention_count"]),
            3,
        ),
        "rework_count": rework_count,
        "rework_rate": round(
            rework_count / reviewed_tasks
            if reviewed_tasks else 0.0,
            3,
        ),
        "avg_rework_per_completed_task": round(
            completed_rework_total / completed_task_count
            if completed_task_count else 0.0,
            3,
        ),
        "junior_count": role_metrics["junior_count"],
        "middle_count": role_metrics["middle_count"],
        "senior_count": role_metrics["senior_count"],
        "junior_avg_knowledge": role_metrics["junior_avg_knowledge"],
        "senior_mentoring_load": role_metrics["senior_mentoring_load"],
        "senior_mentoring_load_per_senior": role_metrics["senior_mentoring_load_per_senior"],
        "junior_help_requests": role_metrics["junior_help_requests"],
        "allocation_match_score": round(
            m.metrics["allocation_match_score_total"] / allocation_count
            if allocation_count else 0.0,
            3,
        ),
        "domain_mismatch_count": m.metrics["domain_mismatch_count"],
        "bottlenecks_detected": m.metrics["bottlenecks_detected"],
        "bottleneck_interventions": m.metrics["bottleneck_interventions"],
        "reassignments": m.metrics["reassignments"],
        "clarification_events": m.metrics["clarification_events"],
        "scope_changes": m.metrics["scope_changes"],
        "scope_changes_prevented": m.metrics["scope_changes_prevented"],
        "pm_capacity_used": m.metrics["pm_capacity_used"],
        "effective_requirement_clarity": round(m.effective_requirement_clarity, 3),
        "attrition_count": m.metrics["attrition_count"],
        "coaching_count": sum(pl.coaching_count for pl in m.pls),
        "remaining_backlog": len(m.backlog),
        "completed_tasks": len(m.completed_tasks),
        "active_developers": len(active),
        "low_energy_count": sum(1 for d in active if d.energy < d.burnout_threshold),
    }

    result = {
        "params": params,
        "snapshots": snapshots,
        "prism": m.get_framework_metrics(),
        "internal_metrics": internal_metrics,
        "total_steps": m.total_steps,
        "num_sprints": m.num_sprints,
    }
    if include_interaction_events:
        result["interaction_events"] = m.interaction_events
    return result


if __name__ == "__main__":
    params = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}
    result = run_simulation(params)
    print(json.dumps(result))
