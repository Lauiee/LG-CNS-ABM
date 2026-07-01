import random
from dataclasses import dataclass, field
from typing import Optional

COMPLEXITY_CONFIG = {
    "C1": {"required_skill": 0.5, "base_steps": 1, "defect_prob": 0.05},
    "C2": {"required_skill": 1.0, "base_steps": 2, "defect_prob": 0.10},
    "C3": {"required_skill": 1.5, "base_steps": 3, "defect_prob": 0.18},
    "C4": {"required_skill": 2.0, "base_steps": 5, "defect_prob": 0.28},
    "C5": {"required_skill": 2.5, "base_steps": 8, "defect_prob": 0.40},
}

DOMAIN_KNOWLEDGE_REQUIREMENT = {
    "C1": 0.2,
    "C2": 0.35,
    "C3": 0.5,
    "C4": 0.65,
    "C5": 0.8,
}

COMPLEXITY_DIST = ["C1"] * 20 + ["C2"] * 35 + ["C3"] * 25 + ["C4"] * 15 + ["C5"] * 5

TASK_TYPE_DIST = (
    ["coding"] * 50 + ["reviewing"] * 20 +
    ["testing"] * 15 + ["deploying"] * 10 + ["incident"] * 5
)

TASK_DOMAINS = ["frontend", "backend", "data", "infra", "legacy", "testing"]

TASK_DOMAIN_DIST = (
    ["backend"] * 30 +
    ["frontend"] * 20 +
    ["data"] * 15 +
    ["infra"] * 10 +
    ["legacy"] * 15 +
    ["testing"] * 10
)

INCIDENT_PRIORITY_DIST = ["Low"] * 40 + ["Medium"] * 30 + ["High"] * 20 + ["Critical"] * 10

INCIDENT_ENERGY_COST = {"Low": 5, "Medium": 10, "High": 20, "Critical": 30}

_task_counter = 0

def _next_id():
    global _task_counter
    _task_counter += 1
    return _task_counter


def _random_from_distribution(distribution, default_distribution):
    source = default_distribution if distribution is None else distribution
    if isinstance(source, dict):
        values = list(source.keys())
        weights = list(source.values())
        return random.choices(values, weights=weights, k=1)[0]
    return random.choice(list(source))


def _random_task_domain(domain_distribution=None) -> str:
    return _random_from_distribution(domain_distribution, TASK_DOMAIN_DIST)


@dataclass
class Task:
    task_id: int = field(default_factory=_next_id)
    task_type: str = "coding"
    complexity: str = "C2"
    domain: str = "backend"
    priority: str = "Medium"          # incident 전용
    status: str = "backlog"           # backlog / in_progress / review_pending / done
    assigned_to: Optional[int] = None
    created_step: int = 0
    completed_step: Optional[int] = None
    progress: float = 0.0             # 0.0 ~ 1.0
    is_new_capability: bool = True    # % Time on New Capabilities 계산용
    caused_by_task_id: Optional[int] = None  # rework 원인 태스크
    help_received_count: int = 0
    rework_count: int = 0
    rework_reason: Optional[str] = None
    origin_task_id: Optional[int] = None

    @property
    def required_skill(self) -> float:
        return COMPLEXITY_CONFIG[self.complexity]["required_skill"]

    @property
    def required_domain_knowledge(self) -> float:
        return DOMAIN_KNOWLEDGE_REQUIREMENT[self.complexity]

    @property
    def base_steps(self) -> int:
        return COMPLEXITY_CONFIG[self.complexity]["base_steps"]

    @property
    def defect_prob(self) -> float:
        return COMPLEXITY_CONFIG[self.complexity]["defect_prob"]

    def effective_steps(self, skill_level: float) -> float:
        """skill이 부족하면 소요 step 증가"""
        if skill_level >= self.required_skill:
            return self.base_steps
        ratio = self.required_skill / max(skill_level, 0.1)
        return self.base_steps * ratio

    def is_complete(self) -> bool:
        return self.progress >= 1.0


def create_random_task(
    step: int,
    task_type: str = None,
    incident_priority: str = None,
    complexity_distribution=None,
    domain_distribution=None,
) -> Task:
    t_type = task_type or random.choice(TASK_TYPE_DIST[:75])  # incident 제외
    complexity = _random_from_distribution(complexity_distribution, COMPLEXITY_DIST)
    is_new = random.random() < 0.6  # 60%는 신규 기능
    return Task(
        task_type=t_type,
        complexity=complexity,
        domain=_random_task_domain(domain_distribution),
        status="backlog",
        created_step=step,
        is_new_capability=is_new,
    )


def create_incident_task(
    step: int,
    priority: str = None,
    caused_by: int = None,
    domain_distribution=None,
) -> Task:
    priority = priority or random.choice(INCIDENT_PRIORITY_DIST)
    complexity_map = {"Low": "C1", "Medium": "C2", "High": "C3", "Critical": "C4"}
    domain = _random_task_domain(domain_distribution)
    return Task(
        task_type="incident",
        complexity=complexity_map[priority],
        domain=domain,
        priority=priority,
        status="backlog",
        created_step=step,
        is_new_capability=False,
        caused_by_task_id=caused_by,
    )
