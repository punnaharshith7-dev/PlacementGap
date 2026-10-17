from __future__ import annotations

from collections import Counter

from pydantic import BaseModel, ConfigDict

from agent.contracts import Plan, PlanRequest


class PlanValidityReport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    valid: bool
    violations: list[str]
    breakdown: dict[str, int]


def check_plan(request: PlanRequest, plan: Plan) -> PlanValidityReport:
    violations: list[str] = []
    counts: Counter[str] = Counter()
    budget = request.weeks * request.hours_per_week
    if plan.total_hours > budget + 1e-8:
        violations.append("hours_over_budget")
    items = [item for week in plan.weeks for item in week.items]
    if abs(plan.total_hours - sum(item.hours for item in items)) > 1e-6:
        violations.append("total_hours_mismatch")
    item_counts = Counter(item.skill_id for item in items)
    for skill_id, count in item_counts.items():
        if count > 1:
            violations.append(f"duplicate_skill:{skill_id}")
    weekly_allocations: dict[str, dict[int, float]] = {}
    for item in items:
        allocations = item.weekly_hours or {item.week: item.hours}
        weekly_allocations[item.skill_id] = allocations
        if abs(sum(allocations.values()) - item.hours) > 1e-6:
            violations.append(f"item_hours_mismatch:{item.skill_id}")
        if any(week < 1 or week > request.weeks or hours <= 0 for week, hours in allocations.items()):
            violations.append(f"allocation_out_of_range:{item.skill_id}")
    declared_weeks = {plan_week.week for plan_week in plan.weeks}
    allocated_weeks = {allocated_week for allocation in weekly_allocations.values() for allocated_week in allocation}
    for allocated_week in allocated_weeks - declared_weeks:
        violations.append(f"allocation_week_missing:{allocated_week}")
    for plan_week in plan.weeks:
        if plan_week.week > request.weeks:
            violations.append(f"week_out_of_range:{plan_week.week}")
        actual_load = sum(allocation.get(plan_week.week, 0.0) for allocation in weekly_allocations.values())
        if abs(plan_week.scheduled_hours - actual_load) > 1e-6:
            violations.append(f"week_sum_mismatch:{plan_week.week}")
        if plan_week.scheduled_hours < 0.8 * request.hours_per_week - 1e-8 or plan_week.scheduled_hours > 1.2 * request.hours_per_week + 1e-8:
            violations.append(f"weekly_load_tolerance:{plan_week.week}")
    scheduled = {item.skill_id: item.week for item in items}
    finish_week = {
        item.skill_id: max(item.weekly_hours, default=item.week)
        for item in items
    }
    deferred = {item.skill_id for item in plan.deferred}
    satisfied = set(plan.satisfied_skills)
    if len(satisfied) != len(plan.satisfied_skills):
        violations.append("duplicate_satisfied_skill")
    if satisfied & (set(scheduled) | deferred):
        violations.append("skill_accounted_more_than_once")
    for item in items:
        for prerequisite in item.prerequisite_ids:
            if prerequisite in scheduled and finish_week[prerequisite] >= item.week:
                violations.append(f"prerequisite_order:{prerequisite}->{item.skill_id}")
            elif prerequisite in deferred:
                violations.append(f"prerequisite_deferred:{prerequisite}->{item.skill_id}")
    accounted = set(scheduled) | deferred | satisfied
    for gap in request.gaps:
        if gap.skill_id not in accounted:
            violations.append(f"unaccounted_gap:{gap.skill_id}")
    for violation in violations:
        counts[violation.split(":", 1)[0]] += 1
    return PlanValidityReport(valid=not violations, violations=violations, breakdown=dict(counts))
