from agent.contracts import Gap, GapVerdict
from agent.scoring import score_gaps


def test_scoring_uses_auditable_weighted_formula_and_unblocking_bonus() -> None:
    base = Gap(skill_id="base", canonical_name="Base", required_level="can_use", demonstrated_level="aware", verdict=GapVerdict.missing, level_delta=1, effort_hours=2, market_demand_weight=0.8, hard_requirement=True, prerequisite_ids=[], evidence=[], rationale="x")
    dependent = Gap(skill_id="dep", canonical_name="Dep", required_level="can_use", demonstrated_level="aware", verdict=GapVerdict.missing, level_delta=1, effort_hours=4, market_demand_weight=0.8, hard_requirement=True, prerequisite_ids=["base"], evidence=[], rationale="x")
    result = score_gaps([dependent, base])
    assert result.gaps[0].skill_id == "base"
    assert result.weight_table["hard_requirement_weight"] > result.weight_table["preferred_requirement_weight"]
    assert result.weight_table["unblocking_bonus"] > 0
