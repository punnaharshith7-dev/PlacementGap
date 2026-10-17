from __future__ import annotations

from typing import Any

from agent.budget import RunBudget
from agent.nodes.common import node_event, state_from, trace_row
from memory.profile_store import get_profile


async def intake_node(raw: dict[str, Any]) -> dict[str, Any]:
    state = state_from(raw)
    if not state.run_id or not state.student_id:
        raise ValueError("run_id and student_id are required")
    if not state.jd_text.strip() and not state.jd_url and not state.role.strip():
        raise ValueError("Provide a pasted JD, live URL, or role name")
    state.source_doc_id = state.source_doc_id or f"profile:{state.student_id}"
    if state.profile is None:
        cached = await get_profile(state.student_id)
        if cached:
            state.profile = cached
    state.status = "running"
    state.budget_snapshot = RunBudget(
        max_usd=state.max_cost_usd,
        max_tokens=state.max_tokens,
    ).snapshot()
    state.events.append(node_event(state, "intake", "node_end", warm_profile=state.profile is not None))
    state.traces.append(trace_row(
        state, "intake", metadata={"warm_profile": state.profile is not None, "tools_allowed": []}
    ))
    return state.model_dump(mode="python")
