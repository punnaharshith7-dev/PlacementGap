from agent.contracts import Gap, GapVerdict, PlanRequest
from agent.solver import build_schedule
from evals.checkers.plan_validity import check_plan


def _gap(skill: str, score: float, effort: float, prereqs: list[str] | None = None) -> Gap:
    return Gap(
        skill_id=skill,
        canonical_name=skill,
        required_level="can_build",
        demonstrated_level="aware",
        verdict=GapVerdict.missing,
        level_delta=2,
        effort_hours=effort,
        priority_score=score,
        prerequisite_ids=prereqs or [],
        evidence=[],
        rationale="test fixture",
    )


def test_solver_respects_prerequisite_order_and_budget() -> None:
    gaps = [_gap("advanced", 10, 3, ["basics"]), _gap("basics", 3, 2)]
    plan = build_schedule(PlanRequest(gaps=gaps, weeks=2, hours_per_week=4))
    assert plan.total_hours <= 8
    assert not plan.violations
    positions = {item.skill_id: week.week for week in plan.weeks for item in week.items}
    if "basics" in positions and "advanced" in positions:
        assert positions["basics"] < positions["advanced"]
    accounted = set(positions) | {item.skill_id for item in plan.deferred}
    assert accounted == {"basics", "advanced"}


def test_solver_emits_deferred_gap_instead_of_dropping_it() -> None:
    plan = build_schedule(PlanRequest(gaps=[_gap("large", 1, 50)], weeks=1, hours_per_week=2))
    assert len(plan.deferred) == 1
    assert plan.deferred[0].skill_id == "large"
    assert plan.deferred[0].reason


def test_solver_does_not_schedule_same_skill_twice() -> None:
    plan = build_schedule(PlanRequest(gaps=[_gap("same", 1, 1), _gap("same", 4, 2)], weeks=2, hours_per_week=3))
    accounted = [item.skill_id for week in plan.weeks for item in week.items]
    accounted.extend(item.skill_id for item in plan.deferred)
    assert accounted.count("same") == 1


def test_solver_splits_large_learning_objective_across_weeks_without_duplicate_items() -> None:
    request = PlanRequest(
        gaps=[_gap("large", 10, 12), _gap("small", 1, 1)],
        weeks=2,
        hours_per_week=8,
    )
    plan = build_schedule(request)

    items = [item for week in plan.weeks for item in week.items]
    assert not plan.deferred
    assert len(items) == 2
    assert len({item.skill_id for item in items}) == 2
    assert sum(items[0].weekly_hours.values()) == items[0].hours
    assert [week.scheduled_hours for week in plan.weeks] == [6.5, 6.5]
    assert check_plan(request, plan).valid


def test_solver_records_skills_already_at_the_required_level_without_study_hours() -> None:
    gap = _gap("python", 1, 1)
    gap.verdict = GapVerdict.has
    gap.level_delta = 0
    request = PlanRequest(gaps=[gap], weeks=4, hours_per_week=8)
    plan = build_schedule(request)

    assert plan.satisfied_skills == ["python"]
    assert plan.weeks == []
    assert plan.deferred == []
    assert check_plan(request, plan).valid
