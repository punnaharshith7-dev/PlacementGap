from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from agent.budget import RunBudget
from agent.contracts import CritiqueItem, PlanRequest, RunState
from agent.llm import LLMClient
from agent.nodes.common import node_event, trace_row
from evals.checkers.plan_validity import check_plan


class CritiqueList(BaseModel):
    model_config = ConfigDict(extra="forbid")
    critiques: list[CritiqueItem] = Field(max_length=100)


_ALLOWED_PARAMETERS = {"effort_multiplier", "priority_multiplier", "defer_skill"}


async def critic_node(raw: dict[str, Any]) -> dict[str, Any]:
    state = RunState.model_validate(raw)
    if not state.plan:
        raise ValueError("Plan critic requires a built plan")
    request = PlanRequest(gaps=state.gaps, weeks=state.weeks, hours_per_week=state.hours_per_week)
    validity = check_plan(request, state.plan)
    critiques: list[CritiqueItem] = []
    for violation in validity.violations:
        category = violation.split(":", 1)[0]
        affected_skill = None
        if category == "weekly_load_tolerance":
            week_id = int(violation.rsplit(":", 1)[-1])
            week = next((item for item in state.plan.weeks if item.week == week_id), None)
            candidates = [item.skill_id for item in week.items] if week else []
            affected_skill = min(
                candidates,
                key=lambda skill_id: next((gap.priority_score for gap in state.gaps if gap.skill_id == skill_id), 0),
                default=None,
            )
            concern = f"{violation}; defer a low-priority objective to restore weekly feasibility."
        elif category.startswith("prerequisite"):
            affected_skill = violation.split("->", 1)[-1] if "->" in violation else None
            concern = violation
        else:
            lowest_priority_gap = min(state.gaps, key=lambda gap: gap.priority_score, default=None)
            affected_skill = lowest_priority_gap.skill_id if lowest_priority_gap else None
            concern = violation
        critiques.append(CritiqueItem(
            category=category,
            skill_id=affected_skill,
            concern=concern,
            adjustment="Defer this objective and rerun the deterministic solver with the remaining gaps.",
            parameter="defer_skill",
            delta=0,
            severity="high",
        ))
    budget = RunBudget.restore(state.budget_snapshot, max_usd=state.max_cost_usd, max_tokens=state.max_tokens)
    client = LLMClient(state.run_id, budget)
    if client.enabled and state.plan:
        proposed, degraded, reason = await client.structured(
            node_name="critic",
            payload=json.dumps({
                "gaps": [gap.model_dump(mode="json") for gap in state.gaps],
                "plan": state.plan.model_dump(mode="json"),
                "weekly_budget_hours": state.hours_per_week,
            }),
            schema=CritiqueList,
            degraded_default=CritiqueList(critiques=[]),
        )
        state.traces.extend(client.traces)
        allowed_skills = {gap.skill_id for gap in state.gaps}
        validated = [
            item for item in proposed.critiques
            if item.parameter in _ALLOWED_PARAMETERS
            and (item.skill_id is None or item.skill_id in allowed_skills)
            and abs(item.delta) <= 1
        ]
        if not degraded:
            critiques = validated or critiques
        else:
            state.degraded = True
            state.degraded_reasons.append(f"Critic used deterministic validity checks: {reason}")
    state.budget_snapshot = budget.snapshot()
    if budget.degraded:
        state.degraded = True
        if budget.reduction_reason and budget.reduction_reason not in state.degraded_reasons:
            state.degraded_reasons.append(budget.reduction_reason)
    state.critique_iteration += 1
    state.critiques = critiques
    if critiques:
        state.unresolved_critiques = critiques[:]
    else:
        state.unresolved_critiques = []
    state.events.append(node_event(
        state,
        "critic",
        "node_end",
        iteration=state.critique_iteration,
        critiques=[item.model_dump(mode="json") for item in critiques],
    ))
    state.traces.append(trace_row(state, "critic", metadata={
        "critic_mode": "liteLLM_or_deterministic_validity_fallback",
        "iterations": state.critique_iteration,
        "critique_count": len(critiques),
        "rubric": "coverage, order, effort, resource level",
        "tools_allowed": [],
    }))
    return state.model_dump(mode="python")
