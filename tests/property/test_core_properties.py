import math

from hypothesis import given
from hypothesis import strategies as st

from agent.budget import RunBudget
from agent.contracts import Gap, GapVerdict, PlanRequest
from agent.solver import build_schedule


@given(
    hours=st.lists(st.floats(min_value=0.25, max_value=4.8, allow_nan=False, allow_infinity=False), min_size=0, max_size=20),
    weeks=st.integers(min_value=1, max_value=8),
    hours_per_week=st.floats(min_value=1, max_value=8, allow_nan=False, allow_infinity=False),
)
def test_solver_never_exceeds_total_capacity_or_duplicates_skills(
    hours: list[float], weeks: int, hours_per_week: float
) -> None:
    gaps = [
        Gap(
            skill_id=f"skill-{index}", canonical_name=f"Skill {index}",
            required_level="can_build", demonstrated_level="aware", verdict=GapVerdict.missing,
            level_delta=2, effort_hours=value, priority_score=float(index), evidence=[], rationale="property",
        )
        for index, value in enumerate(hours)
    ]
    plan = build_schedule(PlanRequest(gaps=gaps, weeks=weeks, hours_per_week=hours_per_week))
    scheduled = [item.skill_id for week in plan.weeks for item in week.items]
    assert len(scheduled) == len(set(scheduled))
    assert plan.total_hours <= weeks * hours_per_week + 1e-8
    assert set(scheduled).isdisjoint(item.skill_id for item in plan.deferred)
    assert set(scheduled) | {item.skill_id for item in plan.deferred} == {gap.skill_id for gap in gaps}


@given(
    calls=st.lists(
        st.tuples(st.integers(min_value=0, max_value=100), st.integers(min_value=0, max_value=100)),
        min_size=0,
        max_size=20,
    )
)
def test_budget_accounting_is_exact(calls: list[tuple[int, int]]) -> None:
    budget = RunBudget(max_usd=1_000, max_tokens=100_000)
    for index, (prompt, completion) in enumerate(calls):
        budget.record(node="node", input_tokens=prompt, output_tokens=completion, cost_usd=index / 1000)
    assert budget.total_tokens == sum(prompt + completion for prompt, completion in calls)
    assert math.isclose(budget.total_usd, sum(index / 1000 for index in range(len(calls))))
