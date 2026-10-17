from __future__ import annotations

import asyncio
from typing import Any

from agent.contracts import PlanRequest, RunState
from agent.nodes.common import node_event, tool_trace, trace_row
from agent.solver import build_schedule
from agent.tools.base import execute_tool
from agent.tools.find_resources import find_resources


async def _resources(state: RunState, gap: Any) -> Any:
    async def get() -> Any:
        return await asyncio.to_thread(
            find_resources,
            gap.skill_id,
            gap.demonstrated_level,
            gap.required_level,
            budget=0,
            max_n=5,
        )

    result = await execute_tool(
        name="find_resources",
        call=get,
        timeout_s=3,
        trace=lambda row: tool_trace(state, "plan_build", {**row, "skill_id": gap.skill_id}),
    )
    return gap.skill_id, result.data or []


async def plan_build_node(raw: dict[str, Any]) -> dict[str, Any]:
    state = RunState.model_validate(raw)
    resources = await asyncio.gather(*[_resources(state, gap) for gap in state.gaps])
    resources_by_skill = dict(resources)
    hours_by_skill = state.plan_edits.get("hours_by_skill", {})
    defer_skill_ids = state.plan_edits.get("defer_skill_ids", [])
    critique_forced_deferred = {
        item.skill_id: item.concern
        for item in state.critiques
        if item.parameter == "defer_skill" and item.skill_id
    }
    effort_multipliers = {
        item.skill_id: max(0.5, min(2.0, 1 + item.delta))
        for item in state.critiques
        if item.skill_id and item.parameter == "effort_multiplier"
    }
    priority_multipliers = {
        item.skill_id: max(0.5, min(2.0, 1 + item.delta))
        for item in state.critiques
        if item.skill_id and item.parameter == "priority_multiplier"
    }
    adjusted_gaps = [
        gap.model_copy(update={
            "effort_hours": max(0.25, min(100.0, float(hours_by_skill.get(gap.skill_id, gap.effort_hours)) * effort_multipliers.get(gap.skill_id, 1.0))),
            "priority_score": gap.priority_score * priority_multipliers.get(gap.skill_id, 1.0),
        })
        for gap in state.gaps
    ]
    request = PlanRequest(
        gaps=adjusted_gaps,
        weeks=state.weeks,
        hours_per_week=state.hours_per_week,
        resources_by_skill=resources_by_skill,
        critique_adjustments={},
        forced_deferred={
            **{str(skill_id): "Deferred at student request during approval review." for skill_id in defer_skill_ids},
            **critique_forced_deferred,
        },
    )
    state.plan = build_schedule(request)
    state.status = "plan_ready"
    state.events.append(node_event(
        state,
        "plan_build",
        "node_end",
        scheduled_hours=state.plan.total_hours,
        deferred=len(state.plan.deferred),
    ))
    state.traces.append(trace_row(state, "plan_build", metadata={
        "deterministic": True,
        "algorithm": state.plan.solver_parameters.get("algorithm"),
        "hours": state.plan.total_hours,
        "budget_hours": state.plan.total_budget_hours,
        "violations": state.plan.violations,
        "tools_allowed": ["estimate_effort", "find_resources", "build_schedule"],
    }))
    return state.model_dump(mode="python")
