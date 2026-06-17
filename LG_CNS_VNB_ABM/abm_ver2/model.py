import random
from mesa import Model, Agent
from tasks import Task, create_random_task, create_incident_task, COMPLEXITY_DIST
from agents import DeveloperAgent, PLAgent
from sampling import ParameterSampler


class SimpleScheduler:
    """Mesa 3.x 호환 간단 스케줄러"""
    def __init__(self, model):
        self.model = model
        self.agents: list[Agent] = []

    def add(self, agent: Agent):
        self.agents.append(agent)

    def remove(self, agent: Agent):
        if agent in self.agents:
            self.agents.remove(agent)

    def step(self):
        order = list(self.agents)
        random.shuffle(order)
        for agent in order:
            agent.step()

SKILL_DISTRIBUTION = [
    (0.5, 1), (1.0, 2), (1.5, 3), (2.0, 2), (2.5, 1)
]

TEAM_COMPOSITIONS = {
    "junior_heavy": {"junior": 5, "middle": 3, "senior": 1},
    "balanced": {"junior": 3, "middle": 4, "senior": 2},
    "senior_heavy": {"junior": 1, "middle": 4, "senior": 4},
}

ROLE_SKILL_LEVELS = {
    "junior": [0.5, 1.0],
    "middle": [1.5, 2.0],
    "senior": [2.5, 3.0],
}


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


class LGCNSDevModel(Model):
    def __init__(
        self,
        num_developers: int = 9,
        num_pl: int = 1,
        num_sprints: int = 6,
        meeting_load: float = 60.0,
        review_strictness: float = 0.7,
        codebase_stability: float = 0.8,
        tech_debt_ratio: float = 0.1,
        pipeline_efficiency: float = 0.7,
        requirement_clarity: float = 0.6,
        communication_overhead: float = 0.3,
        knowledge_decay_rate: float = 0.02,
        collaboration_tendency: float = 0.6,
        sprint_backlog_size: int = 30,
        seed: int = 42,
        sampler=None,
        distribution_overrides=None,
        team_composition: str = None,
        mentoring_intensity: float = None,
        pm_profile: str = None,
        allocation_skill: float = None,
        bottleneck_detection: float = None,
        requirement_coordination: float = None,
        pm_intervention_capacity: int = 2,
    ):
        super().__init__(seed=seed)
        random.seed(seed)
        self.sampler = sampler or ParameterSampler(
            seed=seed,
            distribution_overrides=distribution_overrides,
        )

        # 파라미터
        self.num_developers = num_developers
        self.num_pl = num_pl
        self.num_sprints = num_sprints
        self.total_steps = num_sprints * 10
        self.meeting_load = meeting_load
        self.review_strictness = review_strictness
        self.codebase_stability = codebase_stability
        self.tech_debt_ratio = tech_debt_ratio
        self.pipeline_efficiency = pipeline_efficiency
        self.requirement_clarity = requirement_clarity
        self.communication_overhead = communication_overhead
        self.knowledge_decay_rate = knowledge_decay_rate
        self.collaboration_tendency = collaboration_tendency
        self.sprint_backlog_size = sprint_backlog_size
        self.team_composition = team_composition
        self.role_based_team = team_composition in TEAM_COMPOSITIONS
        self.mentoring_intensity = mentoring_intensity
        self.pm_profile = pm_profile
        self.pm_intervention_enabled = any(
            value is not None
            for value in (
                pm_profile,
                allocation_skill,
                bottleneck_detection,
                requirement_coordination,
            )
        )
        self.allocation_skill = _clamp01(0.5 if allocation_skill is None else allocation_skill)
        self.bottleneck_detection = _clamp01(
            0.5 if bottleneck_detection is None else bottleneck_detection
        )
        self.requirement_coordination = _clamp01(
            0.5 if requirement_coordination is None else requirement_coordination
        )
        self.pm_intervention_capacity = max(0, int(pm_intervention_capacity))
        self.pm_interventions_remaining = self.pm_intervention_capacity
        self.pm_bottleneck_cooldown_steps = 2
        self.last_bottleneck_intervention_step = -self.pm_bottleneck_cooldown_steps
        self.review_defect_reduction = 0.6
        self.review_cost_slope = 0.8
        self.target_wip_per_dev = 5.0
        self.overload_energy_cost = 0.35
        self.overload_motivation_cost = 0.10
        self.team_awareness_buffer = 0.4
        self.max_backlog_pressure = 2.0
        self.baseline_meeting_load = 60.0
        self.meeting_energy_cost = 0.4
        self.meeting_motivation_cost = 0.1
        self.meeting_flow_disruption_prob = 0.08
        self.clarity_defect_reduction = 0.6
        self.effective_requirement_clarity = self._calculate_effective_requirement_clarity()

        # 상태
        self.current_step = 0
        self.current_sprint = 0
        self.running = True
        self.team_tech_debt = tech_debt_ratio
        self.backlog: list[Task] = []
        self.pending_reviews: list[Task] = []
        self.completed_tasks: list[Task] = []

        # 지표
        self.metrics = {
            "prs_per_engineer": {},
            "lead_times": [],
            "deployments": 0,
            "failed_deployments": 0,
            "recovery_times": [],
            "new_capability_steps": 0,
            "total_dev_steps": 0,
            "attrition_count": 0,
            "sprint_velocities": [],
            "help_requests_total": 0,
            "help_requests_resolved": 0,
            "mentoring_load_total": 0.0,
            "knowledge_gained_from_help_total": 0.0,
            "helper_interruptions": 0,
            "allocation_match_score_total": 0.0,
            "allocation_assignment_count": 0,
            "domain_mismatch_count": 0,
            "bottlenecks_detected": 0,
            "bottleneck_interventions": 0,
            "reassignments": 0,
            "clarification_events": 0,
            # 시계열
            "step_history": [],
            "avg_energy_history": [],
            "avg_motivation_history": [],
            "avg_knowledge_history": [],
            "prs_history": [],
            "incident_history": [],
        }

        # 스케줄러
        self.schedule = SimpleScheduler(self)

        # Developer Agent 생성
        self.developers: list[DeveloperAgent] = []
        role_pool = self._build_role_pool(num_developers)
        skill_pool = self._build_skill_pool(num_developers, role_pool)

        for i in range(num_developers):
            role = role_pool[i] if role_pool else None
            skill = skill_pool[i] if i < len(skill_pool) else 1.5
            dev = DeveloperAgent(self, skill_level=skill, sampler=self.sampler, role=role)
            self.developers.append(dev)
            self.schedule.add(dev)

        # PL Agent 생성
        self.pls: list[PLAgent] = []
        devs_per_pl = self.developers[:]
        for _ in range(num_pl):
            pl = PLAgent(self, team_members=devs_per_pl, sampler=self.sampler)
            self.pls.append(pl)
            self.schedule.add(pl)

        # 초기 백로그 생성
        self._generate_backlog(sprint_backlog_size * num_sprints)

    def _build_role_pool(self, num_developers: int):
        if self.team_composition not in TEAM_COMPOSITIONS:
            return None

        role_pool = []
        for role, count in TEAM_COMPOSITIONS[self.team_composition].items():
            role_pool.extend([role] * count)
        while len(role_pool) < num_developers:
            role_pool.append("middle")
        role_pool = role_pool[:num_developers]
        random.shuffle(role_pool)
        return role_pool

    def _sample_skill_for_role(self, role: str) -> float:
        levels = ROLE_SKILL_LEVELS.get(role, [1.5])
        return random.choice(levels)

    def _build_skill_pool(self, num_developers: int, role_pool):
        if role_pool:
            return [self._sample_skill_for_role(role) for role in role_pool]

        skill_pool = []
        for skill, count in SKILL_DISTRIBUTION:
            skill_pool.extend([skill] * count)
        while len(skill_pool) < num_developers:
            skill_pool.append(1.5)
        random.shuffle(skill_pool)
        return skill_pool

    def _generate_backlog(self, count: int):
        for _ in range(count):
            task = create_random_task(0, task_type=random.choice(
                ["coding"] * 50 + ["reviewing"] * 20 + ["testing"] * 15 + ["deploying"] * 10
            ))
            self.backlog.append(task)

    def _calculate_effective_requirement_clarity(self) -> float:
        if not self.pm_intervention_enabled:
            return _clamp01(self.requirement_clarity)
        return _clamp01(
            self.requirement_clarity + 0.35 * self.requirement_coordination
        )

    def pm_requirement_quality_multiplier(self) -> float:
        if not self.pm_intervention_enabled:
            return 1.0
        return max(0.65, 1.0 - 0.30 * self.requirement_coordination)

    def _reset_pm_capacity(self):
        self.pm_interventions_remaining = self.pm_intervention_capacity

    def _consume_pm_capacity(self) -> bool:
        if self.pm_interventions_remaining <= 0:
            return False
        self.pm_interventions_remaining -= 1
        return True

    def should_use_pm_allocation(self) -> bool:
        return (
            self.pm_intervention_enabled and
            random.random() < self.allocation_skill
        )

    def record_task_allocation(
        self,
        developer: DeveloperAgent,
        task: Task,
        pm_optimized: bool = False,
    ):
        match_score = developer.domain_knowledge.get(task.domain, 0.0)
        task.assignment_domain_knowledge = match_score
        task.pm_optimized_allocation = pm_optimized
        task.pm_allocation_progress_multiplier = 1.0
        self.metrics["allocation_match_score_total"] += match_score
        self.metrics["allocation_assignment_count"] += 1
        if match_score < task.required_domain_knowledge:
            self.metrics["domain_mismatch_count"] += 1
            task.assignment_domain_mismatch = True
        else:
            task.assignment_domain_mismatch = False

        if self.pm_intervention_enabled and pm_optimized and not task.assignment_domain_mismatch:
            match_margin = max(0.0, match_score - task.required_domain_knowledge)
            task.pm_allocation_progress_multiplier = 1.0 + min(
                0.16,
                0.05 + 0.12 * self.allocation_skill + 0.05 * match_margin,
            )

    def _find_better_assignee(self, task: Task, current_developer: DeveloperAgent):
        candidates = [
            dev for dev in self.developers
            if dev is not current_developer and
            not dev.attrited and
            dev.current_task is None and
            dev.energy > 30 and
            task.required_skill <= dev.skill_level + 1.0 and
            dev.domain_knowledge.get(task.domain, 0.0) >
            current_developer.domain_knowledge.get(task.domain, 0.0)
        ]
        if not candidates:
            return None
        return max(
            candidates,
            key=lambda dev: (
                dev.domain_knowledge.get(task.domain, 0.0),
                dev.energy,
                dev.skill_level,
            ),
        )

    def _try_reassign_low_progress_task(self, overloaded_devs: list[DeveloperAgent]) -> bool:
        candidates = []
        for dev in overloaded_devs:
            task = dev.current_task
            if task is None or task.task_type == "incident":
                continue
            assigned_step = getattr(task, "assigned_step", task.created_step)
            assignment_age = self.current_step - assigned_step
            slow_threshold = max(4, int(task.base_steps * 2.5))
            if assignment_age < slow_threshold or task.progress >= 0.5:
                continue
            better_assignee = self._find_better_assignee(task, dev)
            if better_assignee is not None:
                candidates.append((dev, better_assignee, task))

        if not candidates:
            return False

        current_dev, new_dev, task = max(
            candidates,
            key=lambda item: item[1].domain_knowledge.get(item[2].domain, 0.0),
        )
        current_dev.current_task = None
        current_dev.state = "Idle"
        current_dev.flow_streak = 0
        new_dev.receive_task(task)
        self.metrics["reassignments"] += 1
        self.metrics["bottleneck_interventions"] += 1
        return True

    def _recover_overloaded_helper(self, overloaded_devs: list[DeveloperAgent]) -> bool:
        if not overloaded_devs:
            return False
        dev = max(
            overloaded_devs,
            key=lambda item: (
                item.mentoring_load,
                item.help_requests_received,
                -item.energy,
            ),
        )
        dev.energy = min(100.0, dev.energy + 4.0)
        dev.motivation = min(100.0, dev.motivation + 0.5)
        self.metrics["bottleneck_interventions"] += 1
        return True

    def _run_pm_bottleneck_intervention(self):
        if not self.pm_intervention_enabled:
            return
        if (
            self.current_step - self.last_bottleneck_intervention_step
            < self.pm_bottleneck_cooldown_steps
        ):
            return
        if random.random() >= self.bottleneck_detection:
            return

        active_devs = [dev for dev in self.developers if not dev.attrited]
        if not active_devs:
            return

        help_total = self.metrics["help_requests_total"]
        help_resolved = self.metrics["help_requests_resolved"]
        resolution_rate = help_resolved / help_total if help_total else 1.0
        active_count = max(len(active_devs), 1)
        backlog_pressure = len(self.backlog) / active_count

        overloaded_devs = [
            dev for dev in active_devs
            if dev.mentoring_load >= 6.0 or dev.help_requests_received >= 4
        ]
        low_progress_devs = [
            dev for dev in active_devs
            if dev.current_task is not None and
            self.current_step - getattr(dev.current_task, "assigned_step", dev.current_task.created_step) >=
            max(4, int(dev.current_task.base_steps * 2.5)) and
            dev.current_task.progress < 0.5
        ]

        bottleneck_detected = bool(
            overloaded_devs or
            low_progress_devs or
            (help_total >= 5 and resolution_rate < 0.6) or
            backlog_pressure > self.target_wip_per_dev * 1.6
        )
        if not bottleneck_detected:
            return

        self.metrics["bottlenecks_detected"] += 1

        if (
            self.pm_interventions_remaining > 0 and
            self._try_reassign_low_progress_task(overloaded_devs + low_progress_devs)
        ):
            self._consume_pm_capacity()
            self.last_bottleneck_intervention_step = self.current_step
            return

        if (
            self.pm_interventions_remaining > 0 and
            self._recover_overloaded_helper(overloaded_devs or low_progress_devs)
        ):
            self._consume_pm_capacity()
            self.last_bottleneck_intervention_step = self.current_step
            return

    def _run_pm_requirement_coordination(self):
        if not self.pm_intervention_enabled:
            return

        active_devs = [dev for dev in self.developers if not dev.attrited]
        if not active_devs:
            return

        unclear_work = any(
            task.status in {"backlog", "in_progress", "review_pending"}
            for task in self.backlog + self.pending_reviews
        )
        if not unclear_work:
            return

        unclear_factor = 1 - self.requirement_clarity
        clarification_prob = min(
            1.0,
            0.05 + 0.15 * self.requirement_coordination + 0.10 * unclear_factor,
        )
        if random.random() >= clarification_prob:
            return
        if not self._consume_pm_capacity():
            return

        self.metrics["clarification_events"] += 1
        for dev in active_devs:
            dev.energy = max(0.0, dev.energy - 0.1)

    def _sprint_start(self):
        self.current_sprint += 1
        sprint_tasks = [t for t in self.backlog if t.status == "backlog"][:self.sprint_backlog_size]
        for pl in self.pls:
            pl.run_sprint_planning(sprint_tasks)

    def _sprint_end(self):
        # 속도 측정
        done_this_sprint = sum(
            1 for t in self.completed_tasks
            if t.completed_step and
            (self.current_step - 10) <= t.completed_step <= self.current_step
        )
        self.metrics["sprint_velocities"].append(done_this_sprint)
        # Retro
        for pl in self.pls:
            pl.run_sprint_retro()

    def _check_incident_spawn(self):
        base_prob = (1 - self.codebase_stability) * 0.15
        effective_prob = max(
            0.0,
            base_prob * (1 - self.review_defect_reduction * self.review_strictness),
        )
        clarity_factor = 1 - self.clarity_defect_reduction * self.effective_requirement_clarity
        effective_prob = max(0.0, effective_prob * clarity_factor)
        effective_prob = max(0.0, effective_prob * self.pm_requirement_quality_multiplier())
        if random.random() < effective_prob:
            priority_weights = {"Low": 0.4, "Medium": 0.3, "High": 0.2, "Critical": 0.1}
            priority = random.choices(
                list(priority_weights.keys()),
                weights=list(priority_weights.values())
            )[0]
            inc = create_incident_task(self.current_step, priority=priority)
            self.backlog.append(inc)
            self.metrics["failed_deployments"] += 1

    def _check_deployments(self):
        deploy_tasks = [t for t in self.backlog if t.task_type == "deploying" and t.status == "backlog"]
        for task in deploy_tasks[:2]:
            task.status = "done"
            task.completed_step = self.current_step
            self.completed_tasks.append(task)
            if task in self.backlog:
                self.backlog.remove(task)
            self.metrics["deployments"] += 1
            if task.is_new_capability:
                self.metrics["new_capability_steps"] += 1
            # Lead Time 기록
            lt = self.current_step - task.created_step
            self.metrics["lead_times"].append(lt)

    def _record_metrics(self):
        active_devs = [d for d in self.developers if not d.attrited]
        if not active_devs:
            return

        avg_energy = sum(d.energy for d in active_devs) / len(active_devs)
        avg_motivation = sum(d.motivation for d in active_devs) / len(active_devs)
        avg_knowledge = sum(d.knowledge for d in active_devs) / len(active_devs)
        total_prs = sum(d.prs_created for d in active_devs)
        incidents = sum(1 for t in self.completed_tasks
                        if t.task_type == "incident" and t.completed_step == self.current_step)

        self.metrics["step_history"].append(self.current_step)
        self.metrics["avg_energy_history"].append(avg_energy)
        self.metrics["avg_motivation_history"].append(avg_motivation)
        self.metrics["avg_knowledge_history"].append(avg_knowledge)
        self.metrics["prs_history"].append(total_prs)
        self.metrics["incident_history"].append(incidents)

        self.metrics["total_dev_steps"] += len(active_devs)

    def _apply_backlog_pressure(self):
        active_devs = [d for d in self.developers if not d.attrited]
        if not active_devs:
            return

        active_dev_count = len(active_devs)
        raw_pressure = max(
            0.0,
            (len(self.backlog) / active_dev_count - self.target_wip_per_dev)
            / self.target_wip_per_dev,
        )
        if not raw_pressure:
            return

        avg_awareness = (
            sum(pl.team_awareness for pl in self.pls) / len(self.pls)
            if self.pls else 0.0
        )
        effective_pressure = raw_pressure * (1 - avg_awareness * self.team_awareness_buffer)
        effective_pressure = min(max(0.0, effective_pressure), self.max_backlog_pressure)
        if not effective_pressure:
            return

        for dev in active_devs:
            dev.energy = max(
                0.0,
                min(100.0, dev.energy - effective_pressure * self.overload_energy_cost),
            )
            dev.motivation = max(
                0.0,
                min(100.0, dev.motivation - effective_pressure * self.overload_motivation_cost),
            )

    def _apply_meeting_pressure(self):
        active_devs = [d for d in self.developers if not d.attrited]
        if not active_devs:
            return

        meeting_pressure = max(
            0.0,
            (self.meeting_load - self.baseline_meeting_load) / self.baseline_meeting_load,
        )
        if not meeting_pressure:
            return

        flow_disruption_prob = min(
            1.0,
            meeting_pressure * self.meeting_flow_disruption_prob,
        )
        for dev in active_devs:
            interrupt_sensitivity_multiplier = 0.5 + dev.interrupt_sensitivity
            dev.energy = max(
                0.0,
                min(
                    100.0,
                    dev.energy
                    - meeting_pressure * self.meeting_energy_cost
                    * interrupt_sensitivity_multiplier,
                ),
            )
            dev.motivation = max(
                0.0,
                min(100.0, dev.motivation - meeting_pressure * self.meeting_motivation_cost),
            )
            if random.random() < flow_disruption_prob:
                dev.flow_streak = 0

    def step(self):
        if self.current_step >= self.total_steps:
            self.running = False
            return

        self.current_step += 1
        self._reset_pm_capacity()

        # Sprint 시작
        if (self.current_step - 1) % 10 == 0:
            self._sprint_start()

        # PM 요구사항 조율
        self._run_pm_requirement_coordination()

        # 환경 이벤트: incident 발생
        self._check_incident_spawn()

        # knowledge decay 적용 (모델 레벨)
        self.team_tech_debt = min(1.0, self.team_tech_debt + 0.001)

        # backlog pressure 적용
        self._apply_backlog_pressure()

        # meeting/interruption pressure 적용
        self._apply_meeting_pressure()

        # Agent 스텝
        self.schedule.step()

        # PM 병목 감지 및 완화
        self._run_pm_bottleneck_intervention()

        # 배포 처리
        self._check_deployments()

        # 지표 기록
        self._record_metrics()

        # Sprint 종료
        if self.current_step % 10 == 0:
            self._sprint_end()

        if self.current_step >= self.total_steps:
            self.running = False

    def get_framework_metrics(self) -> dict:
        """
        PRISM Framework (Productivity Insight & Score Measurement) 정량 지표 6개

        제외 지표:
        - Developer Experience Index: motivation 초기화 → motivation으로 DXI 산출하는 순환 논리
        - Regrettable Attrition: 에너지 소진 단일 원인으로 모델링되어 실제 이탈 원인(연봉,
          커리어, 외부 오퍼 등) 미반영. HR 데이터로 독립 측정 후 ABM 패턴과 사후 상관관계 분석 예정.
        """
        active = [d for d in self.developers if not d.attrited]
        total_devs = max(len(active), 1)
        elapsed = max(self.current_step, 1)

        prs = sum(d.prs_created for d in active)
        prs_per_eng = prs / total_devs

        lead_time = (sum(self.metrics["lead_times"]) / len(self.metrics["lead_times"])
                     if self.metrics["lead_times"] else 0)

        dep_freq = self.metrics["deployments"] / (elapsed / 10)

        cfr = (self.metrics["failed_deployments"] / max(self.metrics["deployments"], 1))

        recovery = (sum(self.metrics["recovery_times"]) / len(self.metrics["recovery_times"])
                    if self.metrics["recovery_times"] else 0)

        new_cap = (self.metrics["new_capability_steps"] /
                   max(self.metrics["total_dev_steps"], 1) * 100)

        return {
            "PRs per Engineer":           round(prs_per_eng, 2),
            "Lead Time (steps)":          round(lead_time, 2),
            "Deployment Frequency":       round(dep_freq, 2),
            "Change Failure Rate (%)":    round(cfr * 100, 1),
            "Recovery Time (steps)":      round(recovery, 2),
            "% Time on New Capabilities": round(new_cap, 1),
        }
