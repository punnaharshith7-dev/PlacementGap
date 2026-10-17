from agent.contracts import Gap, GapVerdict, PlanRequest
from agent.solver import build_schedule
from evals.checkers.plan_validity import check_plan


def test_validity_checker_accepts_solver_output() -> None:
    gap = Gap(skill_id="python", canonical_name="Python", required_level="can_use", demonstrated_level="aware", verdict=GapVerdict.missing, level_delta=1, effort_hours=3, priority_score=1, prerequisite_ids=[], evidence=[], rationale="x")
    request = PlanRequest(gaps=[gap], weeks=2, hours_per_week=2)
    plan = build_schedule(request)
    report = check_plan(request, plan)
    assert report.valid
    assert report.violations == []
