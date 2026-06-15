#!/usr/bin/env python3
"""시뮬레이션 실행 → JSON 데이터 출력"""
import json
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
from model import LGCNSDevModel


def run_simulation(params: dict) -> dict:
    m = LGCNSDevModel(
        num_developers=params.get("num_developers", 9),
        num_sprints=params.get("num_sprints", 6),
        meeting_load=params.get("meeting_load", 60.0),
        review_strictness=params.get("review_strictness", 0.7),
        codebase_stability=params.get("codebase_stability", 0.8),
        collaboration_tendency=params.get("collaboration_tendency", 0.6),
        requirement_clarity=params.get("requirement_clarity", 0.6),
        knowledge_decay_rate=params.get("knowledge_decay_rate", 0.02),
        sprint_backlog_size=params.get("sprint_backlog_size", 30),
        seed=params.get("seed", 42),
        distribution_overrides=params.get("distribution_overrides"),
    )

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
    internal_metrics = {
        "avg_energy": round(sum(d.energy for d in active) / max(len(active), 1), 2),
        "avg_motivation": round(sum(d.motivation for d in active) / max(len(active), 1), 2),
        "min_energy": round(min((d.energy for d in active), default=0), 2),
        "avg_knowledge": round(sum(d.knowledge for d in active) / max(len(active), 1), 2),
        "attrition_count": m.metrics["attrition_count"],
        "coaching_count": sum(pl.coaching_count for pl in m.pls),
        "remaining_backlog": len(m.backlog),
        "completed_tasks": len(m.completed_tasks),
        "active_developers": len(active),
        "low_energy_count": sum(1 for d in active if d.energy < d.burnout_threshold),
    }

    return {
        "params": params,
        "snapshots": snapshots,
        "prism": m.get_framework_metrics(),
        "internal_metrics": internal_metrics,
        "total_steps": m.total_steps,
        "num_sprints": m.num_sprints,
    }


if __name__ == "__main__":
    params = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}
    result = run_simulation(params)
    print(json.dumps(result))
