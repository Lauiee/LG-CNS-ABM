import random
import math
from mesa import Agent
from tasks import Task, create_incident_task, INCIDENT_ENERGY_COST, TASK_DOMAINS

SKILL_PRODUCTIVITY = {0.5: 0.70, 1.0: 0.80, 1.5: 0.90, 2.0: 1.00, 2.5: 1.10, 3.0: 1.25, 5.0: 1.65}

STATES = ["Coding", "FlowCoding", "Reviewing", "Communicating", "Learning", "Interrupted", "Burnout", "Idle"]

HELP_PROGRESS_BOOST = 0.05
HELP_KNOWLEDGE_GAIN = 0.01
HELP_MOTIVATION_GAIN = 1.0
HELPER_ENERGY_COST = 1.5
HELPER_FLOW_RESET_PROB = 0.25

ROLES = ["junior", "middle", "senior"]

STATE_COLORS = {
    "Coding":        "#378ADD",
    "FlowCoding":    "#639922",
    "Reviewing":     "#BA7517",
    "Communicating": "#1D9E75",
    "Learning":      "#1D9E75",
    "Interrupted":   "#D85A30",
    "Burnout":       "#E24B4A",
    "Idle":          "#888780",
}


def _init_mesa_agent(agent, model):
    try:
        Agent.__init__(agent, model)
    except TypeError as exc:
        if "missing 1 required positional argument: 'model'" not in str(exc):
            raise
        next_id = getattr(model, "next_id", None)
        unique_id = next_id() if callable(next_id) else getattr(model, "_next_agent_id", 0) + 1
        if not callable(next_id):
            model._next_agent_id = unique_id
        Agent.__init__(agent, unique_id, model)


def _skill_coeff(skill_level: float) -> float:
    levels = sorted(SKILL_PRODUCTIVITY.keys())
    for i, lv in enumerate(levels):
        if abs(skill_level - lv) < 0.01:
            return SKILL_PRODUCTIVITY[lv]
        if skill_level < lv:
            if i == 0:
                return SKILL_PRODUCTIVITY[lv]
            prev = levels[i - 1]
            t = (skill_level - prev) / (lv - prev)
            return SKILL_PRODUCTIVITY[prev] + t * (SKILL_PRODUCTIVITY[lv] - SKILL_PRODUCTIVITY[prev])
    return SKILL_PRODUCTIVITY[levels[-1]]


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _init_domain_knowledge(skill_level: float) -> dict:
    base = min(1.0, 0.25 + 0.25 * skill_level)
    values = {
        domain: _clamp01(base + random.uniform(-0.12, 0.12))
        for domain in TASK_DOMAINS
    }

    domains = list(TASK_DOMAINS)
    random.shuffle(domains)
    strong_count = random.randint(1, 2)
    weak_count = random.randint(1, 2)

    for domain in domains[:strong_count]:
        values[domain] = _clamp01(values[domain] + random.uniform(0.10, 0.20))
    for domain in domains[strong_count:strong_count + weak_count]:
        values[domain] = _clamp01(values[domain] - random.uniform(0.10, 0.20))

    return values


def _avg_domain_knowledge(domain_knowledge: dict) -> float:
    if not domain_knowledge:
        return 0.0
    return sum(domain_knowledge.values()) / len(domain_knowledge)


def _init_help_seeking_tendency(skill_level: float) -> float:
    return _clamp01(0.8 - 0.18 * skill_level + random.uniform(-0.05, 0.05))


def _init_mentoring_tendency(skill_level: float, domain_knowledge: dict) -> float:
    skill_factor = min(1.0, skill_level / 3.0)
    knowledge_factor = _avg_domain_knowledge(domain_knowledge)
    return _clamp01(0.2 + 0.4 * skill_factor + 0.4 * knowledge_factor + random.uniform(-0.05, 0.05))


def _role_from_skill(skill_level: float) -> str:
    if skill_level <= 1.0:
        return "junior"
    if skill_level >= 2.5:
        return "senior"
    return "middle"


class DeveloperAgent(Agent):
    def __init__(self, model, skill_level: float = 1.5, sampler=None, role: str = None):
        _init_mesa_agent(self, model)
        explicit_role = role in ROLES
        initial_role = role if explicit_role else _role_from_skill(skill_level)
        if sampler is None:
            # 정적 속성
            self.skill_level = skill_level

            # TODO: 추후 아래 주석 기준으로 프레임워크 실측값으로 교체 예정
            # - quality_tendency    ← CFR (개인 단위)
            # - interrupt_sensitivity ← DXI Driver 07 "Deep Work" 점수
            # - burnout_threshold   ← DXI 종합 점수
            # - learning_rate       ← skill_level 연동 유지 (프레임워크 직접 연결 없음)
            noise = lambda: random.uniform(0.9, 1.1)

            self.learning_rate = max(0.1, (0.9 - skill_level * 0.15) * noise())
            self.burnout_threshold = max(10, (30 - skill_level * 3) * noise())
            self.quality_tendency = min(0.95, (0.3 + skill_level * 0.15) * noise())
            self.interrupt_sensitivity = random.uniform(0.3, 0.7)

            # 동적 상태
            self.energy = 100.0
            self.motivation = 70.0
            self.knowledge = min(100.0, skill_level * 20)
            self.flow_streak = 0
            self.accumulated_tech_debt = 0.0
            self.project_experience = _clamp01(0.45 + self.skill_level * 0.08 + random.uniform(-0.10, 0.10))
            self.client_domain_experience = _clamp01(0.42 + self.skill_level * 0.07 + random.uniform(-0.12, 0.12))
            self.prior_collaboration_score = _clamp01(0.55 + random.uniform(-0.15, 0.15))
            self.review_capacity = _clamp(0.35 + self.skill_level * 0.25 + random.uniform(-0.10, 0.10), 0.2, 1.5)
            self.mentoring_capacity = _clamp(0.15 + self.skill_level * 0.35 + random.uniform(-0.10, 0.10), 0.15, 1.5)
        else:
            context = {
                "base_skill_level": skill_level,
                "skill_level": skill_level,
                "role": initial_role,
                "team_composition": getattr(model, "team_composition", None),
                "project_type": getattr(model, "project_type", None),
            }
            self.skill_level = sampler.sample(
                "developer.skill_level",
                default=skill_level,
                context=context,
            )
            context["skill_level"] = self.skill_level
            context["role"] = role if explicit_role else _role_from_skill(self.skill_level)

            # 정적 속성
            self.learning_rate = sampler.sample(
                "developer.learning_rate",
                default=max(0.1, 0.9 - self.skill_level * 0.15),
                context=context,
            )
            self.burnout_threshold = sampler.sample(
                "developer.burnout_threshold",
                default=max(10, 30 - self.skill_level * 3),
                context=context,
            )
            self.quality_tendency = sampler.sample(
                "developer.quality_tendency",
                default=min(0.95, 0.3 + self.skill_level * 0.15),
                context=context,
            )
            self.interrupt_sensitivity = sampler.sample(
                "developer.interrupt_sensitivity",
                default=0.5,
                context=context,
            )

            # 동적 상태
            self.energy = sampler.sample(
                "developer.energy",
                default=100.0,
                context=context,
            )
            self.motivation = sampler.sample(
                "developer.motivation",
                default=70.0,
                context=context,
            )
            self.knowledge = sampler.sample(
                "developer.knowledge",
                default=min(100.0, self.skill_level * 20),
                context=context,
            )
            self.flow_streak = int(sampler.sample(
                "developer.flow_streak",
                default=0,
                context=context,
            ))
            self.accumulated_tech_debt = sampler.sample(
                "developer.accumulated_tech_debt",
                default=0.0,
                context=context,
            )
            self.project_experience = sampler.sample(
                "developer.project_experience",
                default=0.55,
                context=context,
            )
            self.client_domain_experience = sampler.sample(
                "developer.client_domain_experience",
                default=0.55,
                context=context,
            )
            self.prior_collaboration_score = sampler.sample(
                "developer.prior_collaboration_score",
                default=0.58,
                context=context,
            )
            self.review_capacity = sampler.sample(
                "developer.review_capacity",
                default=0.85,
                context=context,
            )
            self.mentoring_capacity = sampler.sample(
                "developer.mentoring_capacity",
                default=0.75,
                context=context,
            )

        self.role = role if explicit_role else _role_from_skill(self.skill_level)
        self.domain_knowledge = _init_domain_knowledge(self.skill_level)
        self.help_seeking_tendency = _init_help_seeking_tendency(self.skill_level)
        self.mentoring_tendency = _init_mentoring_tendency(
            self.skill_level,
            self.domain_knowledge,
        )
        if explicit_role:
            self._apply_role_profile()
        self._apply_experience_profile()

        # 행동 상태
        self.state = "Idle"
        self.current_task: Task = None
        self.burnout_steps = 0
        self.attrited = False

        # 지표 추적
        self.prs_created = 0
        self.tasks_completed = 0
        self.coding_steps = 0
        self.total_steps = 0
        self.interrupted_steps = 0
        self.help_requests_made = 0
        self.help_requests_received = 0
        self.help_requests_resolved = 0
        self.mentoring_load = 0.0
        self.knowledge_gained_from_help = 0.0

    @property
    def skill_coeff(self) -> float:
        return _skill_coeff(self.skill_level)

    @property
    def productivity(self) -> float:
        # AMO(Blumberg & Pringle): Capacity * Willingness * Opportunity
        # Capacity: skill_coeff * energy, Willingness: motivation, Opportunity: knowledge
        e = max(0, self.energy) / 100.0
        m = max(0, self.motivation) / 100.0
        k = max(0, self.knowledge) / 100.0
        return self.skill_coeff * e * m * k

    @property
    def color(self) -> str:
        return STATE_COLORS.get(self.state, "#888780")

    @property
    def effective_mentoring_tendency(self) -> float:
        capacity_factor = 0.75 + 0.25 * min(self.effective_mentoring_capacity, 1.5)
        tendency = self.mentoring_tendency * capacity_factor
        intensity = getattr(self.model, "mentoring_intensity", None)
        if intensity is None:
            return _clamp01(tendency)
        return _clamp01(tendency * intensity)

    @property
    def effective_review_capacity(self) -> float:
        return _clamp(self.review_capacity, 0.2, 1.5)

    @property
    def effective_mentoring_capacity(self) -> float:
        return _clamp(self.mentoring_capacity, 0.15, 1.5)

    def _collaboration_score_with(self, other: "DeveloperAgent") -> float:
        return _clamp01(
            (self.prior_collaboration_score + other.prior_collaboration_score) / 2
        )

    def _communication_cost_multiplier(self, other: "DeveloperAgent") -> float:
        collaboration = self._collaboration_score_with(other)
        overhead = getattr(self.model, "communication_overhead", 0.3)
        return max(0.75, 1.0 + overhead * (1.2 - collaboration) + 0.6 * (1 - collaboration))

    def _help_success_probability(self, helper: "DeveloperAgent") -> float:
        collaboration = self._collaboration_score_with(helper)
        experience = (
            self.project_experience +
            helper.project_experience +
            self.client_domain_experience +
            helper.client_domain_experience
        ) / 4
        capacity = min(helper.effective_mentoring_capacity, 1.5) / 1.5
        overhead = getattr(self.model, "communication_overhead", 0.3)
        return _clamp(
            0.45 + 0.35 * collaboration + 0.15 * capacity + 0.10 * experience - 0.10 * overhead,
            0.15,
            0.98,
        )

    def _help_requester_energy_cost(self, helper: "DeveloperAgent", success: bool) -> float:
        base_cost = 0.6 if success else 1.2
        return base_cost * self._communication_cost_multiplier(helper)

    def _helper_energy_cost(self, helper: "DeveloperAgent") -> float:
        capacity = max(0.4, helper.effective_mentoring_capacity)
        cost = HELPER_ENERGY_COST * self._communication_cost_multiplier(helper) / capacity
        return _clamp(cost, 0.4, 6.0)

    def is_available(self) -> bool:
        return (not self.attrited and
                self.energy > self.burnout_threshold and
                self.current_task is None and
                self.state not in ["Burnout", "Interrupted"])

    def receive_task(self, task: Task):
        self.current_task = task
        task.assigned_to = self.unique_id
        task.assigned_step = getattr(self.model, "current_step", task.created_step)
        task.status = "in_progress"
        self.state = "Coding"
        self.flow_streak = 0

    def _apply_role_profile(self):
        if self.role == "junior":
            self.learning_rate = max(0.1, self.learning_rate * 1.25)
            self.domain_knowledge = {
                domain: _clamp01(value - 0.10)
                for domain, value in self.domain_knowledge.items()
            }
            self.help_seeking_tendency = _clamp01(self.help_seeking_tendency + 0.15)
            self.mentoring_tendency = _clamp01(self.mentoring_tendency - 0.20)
        elif self.role == "senior":
            self.learning_rate = max(0.1, self.learning_rate * 0.85)
            self.domain_knowledge = {
                domain: _clamp01(value + 0.10)
                for domain, value in self.domain_knowledge.items()
            }
            self.help_seeking_tendency = _clamp01(self.help_seeking_tendency - 0.15)
            self.mentoring_tendency = _clamp01(self.mentoring_tendency + 0.20)

    def _apply_experience_profile(self):
        domain_boost = (
            (self.client_domain_experience - 0.5) * 0.16 +
            (self.project_experience - 0.5) * 0.06
        )
        self.domain_knowledge = {
            domain: _clamp01(value + domain_boost)
            for domain, value in self.domain_knowledge.items()
        }
        self.quality_tendency = _clamp01(
            self.quality_tendency + (self.project_experience - 0.5) * 0.08
        )

    def step(self):
        if self.attrited:
            return

        self.total_steps += 1

        # 번아웃 상태 처리
        if self.state == "Burnout":
            self.burnout_steps += 1
            self.motivation = max(0, self.motivation - 2)
            if self.burnout_steps >= 5:
                self.attrited = True
            return

        # 주말 회복 (step % 5 == 0)
        if self.model.current_step % 5 == 0:
            self.energy = min(100, self.energy + 25)
            self.motivation = min(100, self.motivation + 5)

        # 번아웃 체크 (회복 적용 후)
        if self.energy <= self.burnout_threshold:
            self._handle_burnout()
            return

        # motivation 자연 감쇠 — 매우 완만하게
        self.motivation = max(0, self.motivation - 0.2)

        # knowledge decay
        self.knowledge = max(0, self.knowledge * (1 - self.model.knowledge_decay_rate))

        # 상태별 행동
        if self.state in ["Coding", "FlowCoding"]:
            self._do_coding()
        elif self.state == "Reviewing":
            self._do_reviewing()
        elif self.state == "Communicating":
            self._do_communicating()
        elif self.state == "Learning":
            self._do_learning()
        elif self.state == "Interrupted":
            self._recover_from_interrupted()
        elif self.state == "Idle":
            self._idle_learning()

    def _do_coding(self):
        if self.current_task is None:
            self.state = "Idle"
            return

        self.coding_steps += 1
        eff_steps = self.current_task.effective_steps(self.skill_level)
        progress_per_step = self.productivity / max(eff_steps, 0.1)
        progress_per_step *= getattr(self.current_task, "pm_allocation_progress_multiplier", 1.0)
        self.current_task.progress += progress_per_step
        self._maybe_request_help(self.current_task)
        self.energy = max(0, self.energy - 2)  # 코딩 소모 완화

        # tech debt 누적
        td_gain = (1 - self.quality_tendency) * 0.02
        self.accumulated_tech_debt += td_gain
        self.model.team_tech_debt += td_gain

        # FlowCoding 진입
        self.flow_streak += 1
        if self.flow_streak >= 3 and self.energy > 60:
            self.state = "FlowCoding"
            self.energy = max(0, self.energy - 1)  # 몰입 보너스: 소모 적음
        else:
            self.state = "Coding"

        # Task 완료
        if self.current_task.is_complete():
            self._complete_coding_task()

    def _complete_coding_task(self):
        task = self.current_task
        task.status = "review_pending"
        self.prs_created += 1
        self.tasks_completed += 1
        self.motivation = min(100, self.motivation + 5)
        self.current_task = None
        self.state = "Idle"
        self.flow_streak = 0
        self.model.pending_reviews.append(task)
        self.model.metrics["prs_per_engineer"][self.unique_id] = (
            self.model.metrics["prs_per_engineer"].get(self.unique_id, 0) + 1
        )

    def _do_reviewing(self):
        if self.current_task is None:
            self.state = "Idle"
            return
        review_cost_multiplier = max(
            0.1,
            (1 + self.model.review_cost_slope * self.model.review_strictness) *
            getattr(self.model, "quality_gate_cost_multiplier", 1.0),
        )
        review_capacity = self.effective_review_capacity
        self.energy = max(
            0,
            self.energy - 5 * review_cost_multiplier / max(0.6, review_capacity),
        )
        self.current_task.review_progress = getattr(self.current_task, "review_progress", 0.0)
        self.current_task.review_progress += 0.5 * review_capacity / review_cost_multiplier
        if self.current_task.review_progress >= 1.0:
            self._complete_review()

    def _complete_review(self):
        task = self.current_task
        self.current_task = None
        self.state = "Idle"
        self.knowledge = min(100, self.knowledge + 3)
        if task.task_type == "incident" and not getattr(task, "recovery_recorded", False):
            task.completed_step = self.model.current_step
            task.status = "done"
            task.recovery_recorded = True
            recovery_time = max(1, task.completed_step - task.created_step)
            self.model.metrics["recovery_times"].append(recovery_time)
            self.model.completed_tasks.append(task)
            return

        self.model.metrics["reviewed_tasks"] += 1
        # Review strictness lowers escaped defect risk, but makes review slower/costlier.
        defect_chance = max(
            0.0,
            task.defect_prob * (
                1 - self.model.review_defect_reduction * self.model.review_strictness
            ),
        )
        clarity = getattr(
            self.model,
            "effective_requirement_clarity",
            self.model.requirement_clarity,
        )
        clarity_factor = 1 - self.model.clarity_defect_reduction * clarity
        defect_chance = max(0.0, defect_chance * clarity_factor)
        defect_chance = max(
            0.0,
            defect_chance * self.model.pm_requirement_quality_multiplier(),
        )
        defect_chance = max(
            0.0,
            defect_chance * getattr(self.model, "incident_probability_multiplier", 1.0),
        )
        defect_chance = max(
            0.0,
            defect_chance * getattr(self.model, "quality_gate_defect_multiplier", 1.0),
        )
        help_received_count = getattr(task, "help_received_count", 0)
        if help_received_count:
            defect_chance *= max(0.7, 1 - 0.05 * help_received_count)
        defect_found = random.random() < defect_chance
        rework_probability = self._calculate_rework_probability(task, clarity)
        rework_triggered = random.random() < rework_probability
        if rework_triggered:
            self._create_rework_loop(
                task,
                clarity,
                defect_found=defect_found,
                rework_probability=rework_probability,
            )
            return

        if defect_found:
            self._create_incident_from_review_defect(task)
            return

        # 배포 태스크 생성
        from tasks import Task as T
        deploy = T(
            task_type="deploying",
            complexity=task.complexity,
            domain=task.domain,
            status="backlog",
            created_step=task.created_step,
            is_new_capability=task.is_new_capability,
            rework_count=task.rework_count,
            rework_reason=task.rework_reason,
            origin_task_id=task.origin_task_id or task.task_id,
        )
        self.model.backlog.append(deploy)

    def _task_owner(self, task: Task):
        return next(
            (
                dev for dev in self.model.developers
                if dev.unique_id == getattr(task, "assigned_to", None)
            ),
            None,
        )

    def _task_client_domain_experience(self, task: Task) -> float:
        owner = self._task_owner(task)
        owner_experience = getattr(owner, "client_domain_experience", None)
        reviewer_experience = getattr(self, "client_domain_experience", 0.5)
        if owner_experience is None:
            return reviewer_experience
        return min(owner_experience, reviewer_experience)

    def _calculate_rework_probability(self, task: Task, clarity: float) -> float:
        complexity_risk = {
            "C1": 0.02,
            "C2": 0.04,
            "C3": 0.07,
            "C4": 0.11,
            "C5": 0.16,
        }.get(task.complexity, 0.06)
        ambiguity_risk = 0.18 * max(0.0, 1 - clarity)
        domain_mismatch_risk = (
            0.12 if getattr(task, "assignment_domain_mismatch", False) else 0.0
        )
        client_domain_gap = max(0.0, 0.65 - self._task_client_domain_experience(task))
        client_domain_risk = 0.16 * client_domain_gap / 0.65
        volatility_risk = 0.18 * getattr(self.model, "requirement_volatility", 0.0)
        help_reduction = min(0.08, 0.02 * getattr(task, "help_received_count", 0))
        return _clamp(
            complexity_risk +
            ambiguity_risk +
            domain_mismatch_risk +
            client_domain_risk -
            help_reduction +
            volatility_risk,
            0.0,
            0.75,
        )

    def _select_rework_reason(self, task: Task, clarity: float, defect_found: bool) -> str:
        complexity_weight = {
            "C1": 0.05,
            "C2": 0.10,
            "C3": 0.18,
            "C4": 0.28,
            "C5": 0.38,
        }.get(task.complexity, 0.12)
        ambiguity_weight = max(0.05, 1 - clarity)
        review_weight = max(0.05, 1 - self.model.review_strictness)
        if defect_found:
            review_weight += 0.25
        test_weight = 0.20 + (0.20 if task.task_type == "testing" else 0.0)
        domain_weight = 0.35 if getattr(task, "assignment_domain_mismatch", False) else 0.05
        client_gap_weight = max(0.05, 1 - self._task_client_domain_experience(task))
        volatility_weight = max(0.05, getattr(self.model, "requirement_volatility", 0.0))
        reasons = [
            "requirement_ambiguity",
            "review_failure",
            "test_failure",
            "domain_mismatch",
            "client_domain_gap",
            "complexity",
            "requirement_volatility",
        ]
        weights = [
            ambiguity_weight,
            review_weight,
            test_weight,
            domain_weight,
            client_gap_weight,
            complexity_weight,
            volatility_weight,
        ]
        return random.choices(reasons, weights=weights, k=1)[0]

    def _create_rework_loop(
        self,
        task: Task,
        clarity: float,
        defect_found: bool,
        rework_probability: float,
    ):
        reason = self._select_rework_reason(task, clarity, defect_found)
        rollback_range = {
            "requirement_ambiguity": (0.45, 0.70),
            "review_failure": (0.35, 0.60),
            "test_failure": (0.25, 0.45),
            "domain_mismatch": (0.30, 0.55),
            "client_domain_gap": (0.25, 0.50),
            "complexity": (0.20, 0.45),
            "requirement_volatility": (0.30, 0.60),
        }[reason]
        previous_progress = task.progress
        task.rework_count += 1
        task.rework_reason = reason
        task.origin_task_id = task.origin_task_id or task.task_id
        task.status = "backlog"
        task.assigned_to = None
        task.progress = _clamp(
            previous_progress - random.uniform(*rollback_range),
            0.05,
            0.95,
        )
        task.review_progress = 0.0
        self.model.backlog.append(task)
        self.model.metrics["rework_count"] += 1
        rework_by_reason = self.model.metrics.setdefault("rework_by_reason", {})
        rework_by_reason[reason] = rework_by_reason.get(reason, 0) + 1

        self.model.log_interaction(
            "rework_created",
            source_id=self.unique_id,
            task_id=task.task_id,
            domain=task.domain,
            metadata={
                "rework_reason": reason,
                "rework_count": task.rework_count,
                "origin_task_id": task.origin_task_id,
                "defect_found": defect_found,
                "rework_probability": round(rework_probability, 3),
                "previous_progress": round(previous_progress, 3),
                "new_progress": round(task.progress, 3),
            },
        )

    def _create_incident_from_review_defect(self, task: Task):
        incident = create_incident_task(
            self.model.current_step,
            caused_by=task.task_id,
            domain_distribution=getattr(self.model, "domain_distribution", None),
        )
        self.model.backlog.append(incident)
        self.model.metrics["failed_deployments"] += 1

    def _maybe_request_help(self, task: Task):
        current_knowledge = self.domain_knowledge.get(task.domain, 0.0)
        knowledge_gap = max(0.0, task.required_domain_knowledge - current_knowledge)
        if not knowledge_gap:
            return

        help_prob = min(1.0, knowledge_gap * self.help_seeking_tendency)
        if getattr(task, "pm_optimized_allocation", False):
            help_prob *= max(
                0.75,
                1 - 0.20 * getattr(self.model, "allocation_skill", 0.5),
            )
        if random.random() >= help_prob:
            return

        self.help_requests_made += 1
        self.model.metrics["help_requests_total"] += 1

        helper = self._select_helper(task.domain, current_knowledge)
        self.model.log_interaction(
            "help_request",
            source_id=self.unique_id,
            target_id=getattr(helper, "unique_id", None),
            task_id=task.task_id,
            domain=task.domain,
            metadata={
                "knowledge_gap": round(knowledge_gap, 3),
            },
        )
        if helper is None:
            self.model.log_interaction(
                "help_failed",
                source_id=self.unique_id,
                task_id=task.task_id,
                domain=task.domain,
                metadata={
                    "reason": "no_available_helper",
                    "knowledge_gap": round(knowledge_gap, 3),
                },
            )
            return
        intensity = getattr(self.model, "mentoring_intensity", None)
        if intensity is not None and random.random() >= helper.effective_mentoring_tendency:
            self.model.log_interaction(
                "help_failed",
                source_id=self.unique_id,
                target_id=helper.unique_id,
                task_id=task.task_id,
                domain=task.domain,
                metadata={
                    "reason": "helper_not_available_for_mentoring",
                    "mentoring_tendency": round(helper.effective_mentoring_tendency, 3),
                },
            )
            return
        if random.random() >= self._help_success_probability(helper):
            cost = self._help_requester_energy_cost(helper, success=False)
            helper_load = cost * 0.35
            self.energy = max(0, self.energy - cost)
            helper.energy = max(0, helper.energy - helper_load)
            helper.mentoring_load += helper_load
            helper.help_requests_received += 1
            self.model.metrics["mentoring_load_total"] += helper_load
            if helper.current_task is not None:
                self.model.metrics["helper_interruptions"] += 1
            self.model.log_interaction(
                "help_failed",
                source_id=self.unique_id,
                target_id=helper.unique_id,
                task_id=task.task_id,
                domain=task.domain,
                metadata={
                    "reason": "low_help_success_probability",
                    "helper_load": round(helper_load, 3),
                    "requester_cost": round(cost, 3),
                },
            )
            self.model.log_interaction(
                "mentoring",
                source_id=helper.unique_id,
                target_id=self.unique_id,
                task_id=task.task_id,
                domain=task.domain,
                metadata={
                    "outcome": "failed",
                    "helper_load": round(helper_load, 3),
                },
            )
            return

        self._apply_help_success(task, helper)

    def _select_helper(self, domain: str, requester_knowledge: float):
        candidates = [
            dev for dev in self.model.developers
            if dev is not self and
            not dev.attrited and
            dev.domain_knowledge.get(domain, 0.0) > requester_knowledge
        ]
        if not candidates:
            return None
        if getattr(self.model, "pm_intervention_enabled", False):
            load_weight = 0.05 * getattr(self.model, "bottleneck_detection", 0.5)
            return max(
                candidates,
                key=lambda dev: (
                    dev.effective_mentoring_tendency,
                    dev.effective_mentoring_capacity,
                    dev.domain_knowledge.get(domain, 0.0) -
                    dev.mentoring_load * load_weight / max(dev.effective_mentoring_capacity, 0.4),
                    dev.energy,
                ),
            )
        return max(
            candidates,
            key=lambda dev: (
                dev.effective_mentoring_tendency,
                dev.effective_mentoring_capacity,
                dev.domain_knowledge.get(domain, 0.0),
                dev.energy,
            ),
        )

    def _apply_help_success(self, task: Task, helper: "DeveloperAgent"):
        requester_cost = self._help_requester_energy_cost(helper, success=True)
        helper_cost = self._helper_energy_cost(helper)

        task.progress += HELP_PROGRESS_BOOST
        task.help_received_count = getattr(task, "help_received_count", 0) + 1

        new_knowledge = _clamp01(
            self.domain_knowledge.get(task.domain, 0.0) + HELP_KNOWLEDGE_GAIN
        )
        self.domain_knowledge[task.domain] = new_knowledge
        self.knowledge_gained_from_help += HELP_KNOWLEDGE_GAIN
        self.motivation = min(100, self.motivation + HELP_MOTIVATION_GAIN)
        self.energy = max(0, self.energy - requester_cost)
        self.help_requests_resolved += 1

        helper.energy = max(0, helper.energy - helper_cost)
        helper.mentoring_load += helper_cost
        helper.help_requests_received += 1

        self.model.metrics["help_requests_resolved"] += 1
        self.model.metrics["knowledge_gained_from_help_total"] += HELP_KNOWLEDGE_GAIN
        self.model.metrics["mentoring_load_total"] += helper_cost
        self.model.log_interaction(
            "help_success",
            source_id=self.unique_id,
            target_id=helper.unique_id,
            task_id=task.task_id,
            domain=task.domain,
            metadata={
                "helper_cost": round(helper_cost, 3),
                "requester_cost": round(requester_cost, 3),
            },
        )
        self.model.log_interaction(
            "mentoring",
            source_id=helper.unique_id,
            target_id=self.unique_id,
            task_id=task.task_id,
            domain=task.domain,
            metadata={
                "outcome": "success",
                "helper_cost": round(helper_cost, 3),
                "knowledge_gain": HELP_KNOWLEDGE_GAIN,
            },
        )

        if helper.current_task is not None:
            self.model.metrics["helper_interruptions"] += 1
            if random.random() < HELPER_FLOW_RESET_PROB:
                helper.flow_streak = 0

    def _do_communicating(self):
        self.energy = max(0, self.energy - 3)
        self.knowledge = min(100, self.knowledge + 1)
        self.state = "Coding" if self.current_task else "Idle"

    def _do_learning(self):
        self.energy = max(0, self.energy - 2)
        self.knowledge = min(100, self.knowledge + self.learning_rate * 5)
        self.state = "Coding" if self.current_task else "Idle"

    def _recover_from_interrupted(self):
        self.energy = max(0, self.energy - 2)
        self.flow_streak = 0
        self.state = "Coding" if self.current_task else "Idle"

    def _idle_learning(self):
        if random.random() < 0.2:
            self.state = "Learning"

    def _handle_burnout(self):
        self.state = "Burnout"
        self.burnout_steps += 1
        self.motivation = max(0, self.motivation - 5)

    def receive_interrupt(self, energy_cost: int = 4):
        self.energy = max(0, self.energy - energy_cost)
        self.flow_streak = 0
        self.interrupted_steps += 1
        if self.state in ["FlowCoding", "Coding"]:
            self.state = "Interrupted"

    def receive_coaching(self):
        self.motivation = min(100, self.motivation + 10)
        self.energy = min(100, self.energy + 5)

    def transfer_knowledge(self, other: "DeveloperAgent"):
        """확률적 양방향 knowledge 전파"""
        skill_diff = abs(self.skill_level - other.skill_level)
        delta = self.model.collaboration_tendency * 3

        high, low = (self, other) if self.skill_level >= other.skill_level else (other, self)
        direction_bias = 0.5 + 0.5 * (skill_diff / 5.0)

        low.knowledge = min(100, low.knowledge + delta * direction_bias)
        high.knowledge = min(100, high.knowledge + delta * (1 - direction_bias) * 0.5)

        self.energy = max(0, self.energy - 3)
        other.energy = max(0, other.energy - 3)


class PLAgent(Agent):
    def __init__(self, model, team_members: list, sampler=None):
        _init_mesa_agent(self, model)
        self.team_members = team_members
        if sampler is None:
            self.leadership_style = random.uniform(0.5, 1.0)
            self.team_awareness = random.uniform(0.6, 0.9)
        else:
            self.leadership_style = sampler.sample("pl.leadership_style", default=0.75)
            self.team_awareness = sampler.sample("pl.team_awareness", default=0.75)
        self.energy = 100.0
        self.motivation = 80.0
        self.state = "Idle"
        self.team_stress_level = 0.0
        self.coaching_count = 0
        self.allocation_skill = getattr(model, "allocation_skill", 0.5)
        self.bottleneck_detection = getattr(model, "bottleneck_detection", 0.5)
        self.requirement_coordination = getattr(model, "requirement_coordination", 0.5)
        self.scope_control = getattr(model, "scope_control", 0.5)
        self.pm_intervention_capacity = getattr(model, "pm_intervention_capacity", 2)

    @property
    def color(self):
        return "#534AB7"

    def step(self):
        # 주말 회복
        if self.model.current_step % 5 == 0:
            self.energy = min(100, self.energy + 20)

        self.motivation = max(0, self.motivation - 0.3)

        # Daily Standup
        self._run_standup()

        # 번아웃 감지 및 개입 (레이어 1)
        self._detect_and_intervene_burnout()

        # incident 우선순위 판정 및 배정
        self._handle_incidents()

        # Task 배분 (유휴 Developer에게)
        self._assign_tasks()

        # 팀 스트레스 업데이트
        self._update_team_stress()

    def _run_standup(self):
        self.state = "Standup"
        self.energy = max(0, self.energy - 2)
        for dev in self.team_members:
            if not dev.attrited:
                # standup은 가벼운 소모만 — receive_interrupt 호출 제거
                dev.energy = max(0, dev.energy - 2)
                dev.flow_streak = 0  # 흐름만 끊김, 상태 전이는 없음
        self.state = "Idle"

    def _detect_and_intervene_burnout(self):
        for dev in self.team_members:
            if dev.attrited:
                continue
            threshold = dev.burnout_threshold * 1.5
            if dev.energy < threshold:
                if random.random() < self.team_awareness:
                    dev.receive_coaching()
                    self.energy = max(0, self.energy - 5)
                    self.coaching_count += 1
                    self.state = "Coaching"

    def _handle_incidents(self):
        incidents = [t for t in self.model.backlog if t.task_type == "incident" and t.status == "backlog"]
        for inc in incidents:
            available = [d for d in self.team_members if d.is_available()]
            if not available:
                continue
            cost = INCIDENT_ENERGY_COST.get(inc.priority, 10)
            if inc.priority == "Critical":
                for dev in self.team_members:
                    if not dev.attrited:
                        dev.energy = max(0, dev.energy - 15)
                        dev.receive_interrupt(energy_cost=cost)
                        self.model.log_interaction(
                            "incident_interrupt",
                            source_id=self.unique_id,
                            target_id=dev.unique_id,
                            task_id=inc.task_id,
                            domain=inc.domain,
                            metadata={
                                "priority": inc.priority,
                            },
                        )
                assignee = random.choice(available)
            elif inc.priority == "High":
                assignee = random.choice(available)
                assignee.receive_interrupt(energy_cost=cost)
                self.model.log_interaction(
                    "incident_interrupt",
                    source_id=self.unique_id,
                    target_id=assignee.unique_id,
                    task_id=inc.task_id,
                    domain=inc.domain,
                    metadata={
                        "priority": inc.priority,
                    },
                )
            else:
                assignee = min(available, key=lambda d: d.energy)
                assignee.energy = max(0, assignee.energy - cost)
            assignee.receive_task(inc)
            self.model.log_interaction(
                "incident_assignment",
                source_id=self.unique_id,
                target_id=assignee.unique_id,
                task_id=inc.task_id,
                domain=inc.domain,
                metadata={
                    "priority": inc.priority,
                },
            )
            self.model.backlog.remove(inc)

    def _candidate_tasks_for_dev(self, dev, backlog_tasks: list[Task]) -> list[Task]:
        suitable = [
            task for task in backlog_tasks
            if task.required_skill <= dev.skill_level + 1.0
        ]
        return suitable if suitable else backlog_tasks[:1]

    def _choose_existing_assignment_task(self, dev, backlog_tasks: list[Task]):
        suitable = self._candidate_tasks_for_dev(dev, backlog_tasks)
        if not suitable:
            return None

        # knowledge 높은 dev에게 C4/C5 우선
        high_complexity = [t for t in suitable if t.complexity in ["C4", "C5"]]
        if high_complexity and dev.knowledge > 60:
            return random.choice(high_complexity)

        low_suitable = [t for t in suitable if t.complexity not in ["C4", "C5"]]
        return random.choice(low_suitable) if low_suitable else random.choice(suitable)

    def _choose_pm_best_fit_assignment(self, available_devs, backlog_tasks):
        candidates = []
        for dev in available_devs:
            for task in self._candidate_tasks_for_dev(dev, backlog_tasks):
                domain_knowledge = dev.domain_knowledge.get(task.domain, 0.0)
                knowledge_gap = max(0.0, task.required_domain_knowledge - domain_knowledge)
                skill_fit = max(0.0, 1.0 - abs(task.required_skill - dev.skill_level) / 3.0)
                energy_fit = max(0.0, min(1.0, dev.energy / 100.0))
                load_fit = max(0.0, 1.0 - min(1.0, dev.mentoring_load / 20.0))
                task_size_fit = max(0.0, 1.0 - (task.base_steps - 1) / 7.0)
                balance_fit = 1.0 / (1.0 + dev.tasks_completed)
                score = (
                    domain_knowledge * 0.42 +
                    skill_fit * 0.20 +
                    energy_fit * 0.14 +
                    load_fit * 0.10 +
                    task_size_fit * 0.10 +
                    balance_fit * 0.04 -
                    knowledge_gap * 0.35
                )
                candidates.append((
                    score,
                    domain_knowledge,
                    energy_fit,
                    task_size_fit,
                    dev,
                    task,
                ))
        if not candidates:
            return None, None
        _, _, _, _, dev, task = max(candidates, key=lambda item: item[:4])
        return dev, task

    def _assign_task_to_dev(self, dev, task, backlog_tasks: list[Task], pm_optimized: bool = False):
        dev.receive_task(task)
        self.model.record_task_allocation(dev, task, pm_optimized=pm_optimized)
        self.model.log_interaction(
            "task_assignment",
            source_id=self.unique_id,
            target_id=dev.unique_id,
            task_id=task.task_id,
            domain=task.domain,
            metadata={
                "task_type": task.task_type,
                "complexity": task.complexity,
                "pm_optimized": pm_optimized,
            },
        )
        if task in backlog_tasks:
            backlog_tasks.remove(task)
        if task in self.model.backlog:
            self.model.backlog.remove(task)

    def _assign_tasks(self):
        available_devs = [
            dev for dev in self.team_members
            if dev.is_available() and dev.energy > 30
        ]
        had_available_devs = bool(available_devs)
        backlog_tasks = [
            task for task in self.model.backlog
            if task.status == "backlog" and task.task_type != "incident"
        ]

        while available_devs and backlog_tasks:
            pm_optimized = False
            if self.model.should_use_pm_allocation():
                dev, task = self._choose_pm_best_fit_assignment(available_devs, backlog_tasks)
                pm_optimized = True
            else:
                dev = available_devs[0]
                task = self._choose_existing_assignment_task(dev, backlog_tasks)

            if dev is None or task is None:
                break

            self._assign_task_to_dev(dev, task, backlog_tasks, pm_optimized=pm_optimized)
            available_devs.remove(dev)
        self.state = "TaskAssigning" if had_available_devs else "Idle"

    def _assign_reviewer(self, task):
        candidates = [d for d in self.team_members
                      if not d.attrited and d.energy > 30 and d.current_task is None]
        if not candidates:
            return
        reviewer = max(
            candidates,
            key=lambda d: (
                d.effective_review_capacity,
                d.domain_knowledge.get(task.domain, 0.0),
                d.skill_level,
                d.energy,
            ),
        )
        reviewer.current_task = task
        reviewer.state = "Reviewing"
        task.review_progress = 0.0
        task.status = "in_progress"
        self.model.log_interaction(
            "review_assignment",
            source_id=self.unique_id,
            target_id=reviewer.unique_id,
            task_id=task.task_id,
            domain=task.domain,
            metadata={
                "review_capacity": round(reviewer.effective_review_capacity, 3),
            },
        )

    def _update_team_stress(self):
        active = [d for d in self.team_members if not d.attrited]
        if active:
            self.team_stress_level = 1 - (sum(d.energy for d in active) / len(active)) / 100

    def run_sprint_planning(self, sprint_backlog: list):
        self.state = "Planning"
        self.energy = max(0, self.energy - 5)
        for dev in self.team_members:
            if not dev.attrited:
                dev.energy = max(0, dev.energy - 3)
        # 리뷰 배정
        for task in list(self.model.pending_reviews):
            self._assign_reviewer(task)
            self.model.pending_reviews.remove(task)
        self.state = "Idle"

    def run_sprint_retro(self):
        self.state = "Retrospective"
        active = [d for d in self.team_members if not d.attrited]
        if not active:
            return
        avg_energy = sum(d.energy for d in active) / len(active)
        avg_motivation = sum(d.motivation for d in active) / len(active)

        # 팀 상태 나쁘면 다음 스프린트 조정
        if avg_energy < 40:
            self.model.sprint_backlog_size = max(10, self.model.sprint_backlog_size - 5)
        if avg_motivation < 30:
            self.model.review_strictness = max(0.3, self.model.review_strictness - 0.1)

        # motivation 보너스
        for dev in active:
            dev.motivation = min(100, dev.motivation + 5)
            dev.energy = max(0, dev.energy - 5)

        # Attrition 처리
        for dev in list(self.team_members):
            if dev.attrited:
                self.team_members.remove(dev)
                self.model.metrics["attrition_count"] += 1
                replacement_role = getattr(dev, "role", None) if getattr(self.model, "role_based_team", False) else None
                replacement_skill = (
                    self.model._sample_skill_for_role(replacement_role)
                    if replacement_role and callable(getattr(self.model, "_sample_skill_for_role", None))
                    else 1.0
                )
                new_dev = DeveloperAgent(
                    self.model,
                    skill_level=replacement_skill,
                    sampler=getattr(self.model, "sampler", None),
                    role=replacement_role,
                )
                self.team_members.append(new_dev)
                self.model.schedule.add(new_dev)

        self.state = "Idle"
