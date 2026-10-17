from __future__ import annotations

from dataclasses import dataclass

from agent.contracts import Gap
from ontology.graph import SkillGraph


@dataclass(frozen=True)
class ScoringResult:
    gaps: list[Gap]
    weight_table: dict[str, float]


def score_gaps(gaps: list[Gap]) -> ScoringResult:
    """Score gaps deterministically using the documented auditable formula."""
    hard_weight = 1.0
    preferred_weight = 0.65
    unblocking_bonus = 0.25
    dependents: dict[str, int] = {}
    for gap in gaps:
        for prerequisite in gap.prerequisite_ids:
            dependents[prerequisite] = dependents.get(prerequisite, 0) + 1
    graph = SkillGraph()
    prerequisite_depth = {gap.skill_id: graph.prerequisite_depth(gap.skill_id) for gap in gaps}

    scored: list[Gap] = []
    for gap in gaps:
        requirement_weight = hard_weight if gap.hard_requirement else preferred_weight
        effort = max(gap.effort_hours, 0.25)
        base = (
            requirement_weight
            * gap.market_demand_weight
            * gap.level_delta
            * (1.0 / effort)
        )
        unblock = unblocking_bonus * dependents.get(gap.skill_id, 0)
        scored.append(gap.model_copy(update={"priority_score": round(base + unblock, 6)}))

    ordered = sorted(
        scored,
        key=lambda item: (
            -item.priority_score,
            -prerequisite_depth.get(item.skill_id, 0),
            -item.level_delta,
            item.effort_hours,
            item.skill_id,
        ),
    )
    return ScoringResult(
        gaps=ordered,
        weight_table={
            "hard_requirement_weight": hard_weight,
            "preferred_requirement_weight": preferred_weight,
            "unblocking_bonus": unblocking_bonus,
            "formula_market_demand_multiplier": 1.0,
            "formula_level_delta_multiplier": 1.0,
            "formula_inverse_effort_multiplier": 1.0,
            "prerequisite_depth_tiebreak": 1.0,
        },
    )
