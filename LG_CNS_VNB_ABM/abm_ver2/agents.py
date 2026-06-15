import random
import math
from mesa import Agent
from tasks import Task, create_incident_task, INCIDENT_ENERGY_COST

SKILL_PRODUCTIVITY = {0.5: 0.70, 1.0: 0.80, 1.5: 0.90, 2.0: 1.00, 2.5: 1.10, 3.0: 1.25, 5.0: 1.65}

STATES = ["Coding", "FlowCoding", "Reviewing", "Communicating", "Learning", "Interrupted", "Burnout", "Idle"]

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


class DeveloperAgent(Agent):
    def __init__(self, model, skill_level: float = 1.5, sampler=None):
        _init_mesa_agent(self, model)
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
        else:
            context = {"base_skill_level": skill_level, "skill_level": skill_level}
            self.skill_level = sampler.sample(
                "developer.skill_level",
                default=skill_level,
                context=context,
            )
            context["skill_level"] = self.skill_level

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

    def is_available(self) -> bool:
        return (not self.attrited and
                self.energy > self.burnout_threshold and
                self.current_task is None and
                self.state not in ["Burnout", "Interrupted"])

    def receive_task(self, task: Task):
        self.current_task = task
        task.assigned_to = self.unique_id
        task.status = "in_progress"
        self.state = "Coding"
        self.flow_streak = 0

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
        self.current_task.progress += progress_per_step
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
            1 + self.model.review_cost_slope * self.model.review_strictness,
        )
        self.energy = max(0, self.energy - 5 * review_cost_multiplier)
        self.current_task.review_progress = getattr(self.current_task, "review_progress", 0.0)
        self.current_task.review_progress += 0.5 / review_cost_multiplier
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

        # Review strictness lowers escaped defect risk, but makes review slower/costlier.
        defect_chance = max(
            0.0,
            task.defect_prob * (
                1 - self.model.review_defect_reduction * self.model.review_strictness
            ),
        )
        clarity_factor = 1 - self.model.clarity_defect_reduction * self.model.requirement_clarity
        defect_chance = max(0.0, defect_chance * clarity_factor)
        if random.random() < defect_chance:
            incident = create_incident_task(self.model.current_step, caused_by=task.task_id)
            self.model.backlog.append(incident)
            self.model.metrics["failed_deployments"] += 1
        else:
            # 배포 태스크 생성
            from tasks import Task as T
            deploy = T(
                task_type="deploying",
                complexity=task.complexity,
                status="backlog",
                created_step=task.created_step,
                is_new_capability=task.is_new_capability,
            )
            self.model.backlog.append(deploy)

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
                assignee = random.choice(available)
            elif inc.priority == "High":
                assignee = random.choice(available)
                assignee.receive_interrupt(energy_cost=cost)
            else:
                assignee = min(available, key=lambda d: d.energy)
                assignee.energy = max(0, assignee.energy - cost)
            assignee.receive_task(inc)
            self.model.backlog.remove(inc)

    def _assign_tasks(self):
        available_devs = [d for d in self.team_members
                          if d.is_available() and d.energy > 30]
        backlog_tasks = [t for t in self.model.backlog
                         if t.status == "backlog" and t.task_type != "incident"]

        for dev in available_devs:
            if not backlog_tasks:
                break
            # complexity ≤ skill+1 범위 필터
            suitable = [t for t in backlog_tasks
                        if t.required_skill <= dev.skill_level + 1.0]
            if not suitable:
                suitable = backlog_tasks[:1]

            # knowledge 높은 dev에게 C4/C5 우선
            high_complexity = [t for t in suitable if t.complexity in ["C4", "C5"]]
            if high_complexity and dev.knowledge > 60:
                task = random.choice(high_complexity)
            else:
                low_suitable = [t for t in suitable if t.complexity not in ["C4", "C5"]]
                task = random.choice(low_suitable) if low_suitable else random.choice(suitable)

            dev.receive_task(task)
            backlog_tasks.remove(task)
            if task in self.model.backlog:
                self.model.backlog.remove(task)
        self.state = "TaskAssigning" if available_devs else "Idle"

    def _assign_reviewer(self, task):
        candidates = [d for d in self.team_members
                      if not d.attrited and d.energy > 30 and d.current_task is None]
        if not candidates:
            return
        reviewer = max(candidates, key=lambda d: d.skill_level)
        reviewer.current_task = task
        reviewer.state = "Reviewing"
        task.review_progress = 0.0
        task.status = "in_progress"

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
                new_dev = DeveloperAgent(
                    self.model,
                    skill_level=1.0,
                    sampler=getattr(self.model, "sampler", None),
                )
                self.team_members.append(new_dev)
                self.model.schedule.add(new_dev)

        self.state = "Idle"
