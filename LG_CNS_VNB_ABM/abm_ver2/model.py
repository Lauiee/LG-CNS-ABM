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
        clarity_factor = 1 - self.clarity_defect_reduction * self.requirement_clarity
        effective_prob = max(0.0, effective_prob * clarity_factor)
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

        # Sprint 시작
        if (self.current_step - 1) % 10 == 0:
            self._sprint_start()

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
