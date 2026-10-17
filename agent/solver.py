from __future__ import annotations

import heapq
from collections import defaultdict, deque
from math import ceil, floor

from agent.contracts import DeferredGap, Gap, GapVerdict, Plan, PlanItem, PlanRequest, PlanWeek


def _topological_rank(request: PlanRequest) -> dict[str, int]:
    by_id = {gap.skill_id: gap for gap in request.gaps}
    indegree = {skill_id: 0 for skill_id in by_id}
    children: dict[str, list[str]] = defaultdict(list)
    for gap in request.gaps:
        for prerequisite in gap.prerequisite_ids:
            if prerequisite in by_id and prerequisite != gap.skill_id:
                children[prerequisite].append(gap.skill_id)
                indegree[gap.skill_id] += 1
    queue = deque(sorted(skill_id for skill_id, degree in indegree.items() if degree == 0))
    rank: dict[str, int] = {}
    while queue:
        current = queue.popleft()
        rank[current] = max(
            (rank.get(parent, 0) + 1 for parent in by_id[current].prerequisite_ids if parent in rank),
            default=0,
        )
        for child in sorted(children[current]):
            indegree[child] -= 1
            if indegree[child] == 0:
                queue.append(child)
    for skill_id in by_id:
        rank.setdefault(skill_id, 0)
    return rank


def build_schedule(request: PlanRequest) -> Plan:
    """Greedy score ordering with topological multi-week allocation and local search."""
    weekly = request.hours_per_week
    total_budget = request.weeks * weekly
    lower, upper = weekly * 0.8, weekly * 1.2
    gaps: dict[str, Gap] = {}
    for gap in request.gaps:
        if gap.skill_id not in gaps or gap.priority_score > gaps[gap.skill_id].priority_score:
            gaps[gap.skill_id] = gap
    rank = _topological_rank(request)
    ordered = _topological_order(gaps)
    deferred_by_id: dict[str, DeferredGap] = {
        gap.skill_id: DeferredGap(
            skill_id=gap.skill_id,
            canonical_name=gap.canonical_name,
            reason=request.forced_deferred[gap.skill_id],
            estimated_hours=gap.effort_hours,
        )
        for gap in ordered
        if gap.skill_id in request.forced_deferred
    }
    satisfied_skills = [
        gap.skill_id for gap in ordered
        if gap.verdict == GapVerdict.has and gap.skill_id not in deferred_by_id
    ]
    actionable = {
        gap.skill_id: gap for gap in ordered
        if gap.skill_id not in satisfied_skills and gap.skill_id not in deferred_by_id
    }
    selected = [gap for gap in ordered if gap.skill_id in actionable]
    allocation: tuple[list[PlanItem], dict[int, float], int] | None = None

    while selected:
        allocation = _allocate(selected, actionable, request)
        if allocation is not None:
            break
        selected_ids = {gap.skill_id for gap in selected}
        blocked = [
            gap for gap in selected
            if any(prerequisite in gaps and prerequisite not in selected_ids for prerequisite in gap.prerequisite_ids)
        ]
        victim = min(
            blocked or selected,
            key=lambda gap: (gap.priority_score, -rank.get(gap.skill_id, 0), gap.skill_id),
        )
        removed_ids = {victim.skill_id}
        # Removing a prerequisite also removes its dependents, so no partial chain can leak through.
        changed = True
        while changed:
            changed = False
            for gap in selected:
                if gap.skill_id not in removed_ids and any(item in removed_ids for item in gap.prerequisite_ids):
                    removed_ids.add(gap.skill_id)
                    changed = True
        for skill_id in removed_ids:
            gap = gaps[skill_id]
            dependency = next((item for item in gap.prerequisite_ids if item in removed_ids), None)
            reason = (
                f"Prerequisite {dependency} was deferred by the horizon and weekly-load constraints."
                if skill_id != victim.skill_id and dependency
                else f"No complete topological allocation fits the {request.weeks}-week horizon and 80/20 weekly-load band."
            )
            deferred_by_id[skill_id] = DeferredGap(
                skill_id=skill_id,
                canonical_name=gap.canonical_name,
                reason=reason,
                estimated_hours=gap.effort_hours,
            )
        selected = [gap for gap in selected if gap.skill_id not in removed_ids]

    items, loads, active_weeks = allocation or ([], {}, 0)
    planned = [
        PlanWeek(
            week=week,
            capacity_hours=weekly,
            scheduled_hours=loads.get(week, 0.0),
            items=[item for item in items if item.week == week],
        )
        for week in range(1, active_weeks + 1)
    ]
    violations: list[str] = []
    if sum(loads.values()) > total_budget + 1e-9:
        violations.append("Total schedule exceeds the requested hour budget.")
    for week in planned:
        if week.scheduled_hours < lower - 1e-9 or week.scheduled_hours > upper + 1e-9:
            violations.append(f"Week {week.week} load {week.scheduled_hours:g}h outside {lower:g}-{upper:g}h tolerance.")
    assigned = {item.skill_id: item.week for item in items}
    for item in items:
        for prerequisite in item.prerequisite_ids:
            if prerequisite in assigned and assigned[prerequisite] >= item.week:
                violations.append(f"Prerequisite {prerequisite} is not strictly before {item.skill_id}.")
    for gap in ordered:
        if gap.skill_id not in assigned and gap.skill_id not in deferred_by_id and gap.skill_id not in satisfied_skills:
            deferred_by_id[gap.skill_id] = DeferredGap(
                skill_id=gap.skill_id,
                canonical_name=gap.canonical_name,
                reason="Could not be placed by the deterministic solver.",
                estimated_hours=gap.effort_hours,
            )
    deferred = [deferred_by_id[gap.skill_id] for gap in ordered if gap.skill_id in deferred_by_id]
    total_hours = sum(loads.values())
    return Plan(
        weeks=planned,
        deferred=deferred,
        satisfied_skills=satisfied_skills,
        total_hours=total_hours,
        total_budget_hours=round(total_budget, 2),
        violations=violations,
        solver_parameters={
            "algorithm": "greedy_score_topological_multiweek_with_local_search",
            "lower_weekly_load_hours": round(lower, 2),
            "upper_weekly_load_hours": round(upper, 2),
            "duplicate_skill_policy": "keep_highest_priority_score",
            "multi_week_tasks": True,
            "critique_adjustments": dict(request.critique_adjustments),
        },
    )


def _topological_order(gaps: dict[str, Gap]) -> list[Gap]:
    indegree = {skill_id: 0 for skill_id in gaps}
    children: dict[str, list[str]] = defaultdict(list)
    for gap in gaps.values():
        for prerequisite in gap.prerequisite_ids:
            if prerequisite in gaps and prerequisite != gap.skill_id:
                children[prerequisite].append(gap.skill_id)
                indegree[gap.skill_id] += 1
    ready = [
        (-gap.priority_score, -gap.level_delta, gap.skill_id)
        for skill_id, gap in gaps.items()
        if indegree[skill_id] == 0
    ]
    heapq.heapify(ready)
    result: list[Gap] = []
    while ready:
        _, _, skill_id = heapq.heappop(ready)
        result.append(gaps[skill_id])
        for child in sorted(children[skill_id]):
            indegree[child] -= 1
            if indegree[child] == 0:
                gap = gaps[child]
                heapq.heappush(ready, (-gap.priority_score, -gap.level_delta, gap.skill_id))
    included = {gap.skill_id for gap in result}
    result.extend(
        sorted(
            (gap for skill_id, gap in gaps.items() if skill_id not in included),
            key=lambda gap: (-gap.priority_score, -gap.level_delta, gap.skill_id),
        )
    )
    return result


def _allocate(
    selected: list[Gap], all_gaps: dict[str, Gap], request: PlanRequest
) -> tuple[list[PlanItem], dict[int, float], int] | None:
    total = sum(gap.effort_hours for gap in selected)
    if total <= 1e-9 or total > request.weeks * request.hours_per_week + 1e-9:
        return None
    lower = request.hours_per_week * 0.8
    upper = request.hours_per_week * 1.2
    min_weeks = max(1, ceil(total / upper - 1e-9))
    max_weeks = min(request.weeks, floor(total / lower + 1e-9))
    if min_weeks > max_weeks:
        return None
    target_weeks = round(total / request.hours_per_week)
    active_weeks = min(max(target_weeks, min_weeks), max_weeks)
    target = total / active_weeks
    loads = {week: 0.0 for week in range(1, active_weeks + 1)}
    finish_week: dict[str, int] = {}
    items: list[PlanItem] = []
    for gap in selected:
        needed = [prereq for prereq in gap.prerequisite_ids if prereq in all_gaps]
        if any(prerequisite not in finish_week for prerequisite in needed):
            return None
        earliest = max((finish_week[prerequisite] + 1 for prerequisite in needed), default=1)
        if earliest > active_weeks:
            return None
        remaining = gap.effort_hours
        weekly_hours: dict[int, float] = {}
        while remaining > 1e-8:
            available = [
                week for week in range(earliest, active_weeks + 1)
                if loads[week] < target - 1e-8
            ]
            if not available:
                return None
            chosen = min(available, key=lambda week: (loads[week], week))
            amount = min(remaining, target - loads[chosen])
            weekly_hours[chosen] = weekly_hours.get(chosen, 0.0) + amount
            loads[chosen] += amount
            remaining -= amount
        start_week = min(weekly_hours)
        finish_week[gap.skill_id] = max(weekly_hours)
        items.append(PlanItem(
            skill_id=gap.skill_id,
            canonical_name=gap.canonical_name,
            week=start_week,
            hours=gap.effort_hours,
            weekly_hours=weekly_hours,
            outcome=f"Demonstrate {gap.required_level.value} proficiency in {gap.canonical_name}.",
            prerequisite_ids=gap.prerequisite_ids,
            resources=request.resources_by_skill.get(gap.skill_id, []),
            evidence=gap.evidence,
        ))

    _local_search(items, loads, target, lower, upper)
    if any(load < lower - 1e-7 or load > upper + 1e-7 for load in loads.values()):
        return None
    return items, loads, active_weeks


def _local_search(
    items: list[PlanItem], loads: dict[int, float], target: float, lower: float, upper: float
) -> None:
    """Move hours only within an item's current span to reduce weekly-load variance."""
    del lower, upper  # Candidate moves stay inside the validated target band.
    for _ in range(max(1, len(items) * len(loads))):
        base_error = sum((load - target) ** 2 for load in loads.values())
        best: tuple[float, PlanItem, int, int, float] | None = None
        for item in items:
            first, last = min(item.weekly_hours), max(item.weekly_hours)
            for source, source_amount in sorted(item.weekly_hours.items()):
                for destination in range(first, last + 1):
                    if (
                        destination == source
                        or destination not in item.weekly_hours
                        or loads[destination] >= target - 1e-8
                    ):
                        continue
                    keep = 1e-7 if source in {first, last} else 0.0
                    difference = loads[source] - loads[destination]
                    amount = min(source_amount - keep, target - loads[destination], difference / 2)
                    if amount <= 1e-8:
                        continue
                    error = base_error - difference * difference / 2 + (difference - 2 * amount) ** 2 / 2
                    if error < base_error - 1e-10 and (best is None or error < best[0]):
                        best = (error, item, source, destination, amount)
        if best is None:
            return
        _, item, source, destination, amount = best
        item.weekly_hours[source] -= amount
        item.weekly_hours[destination] = item.weekly_hours.get(destination, 0.0) + amount
        loads[source] -= amount
        loads[destination] += amount
