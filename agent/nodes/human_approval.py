from __future__ import annotations

from typing import Any

from langgraph.types import interrupt

from agent.contracts import RunState
from agent.nodes.common import node_event, trace_row


async def human_approval_node(raw: dict[str, Any]) -> dict[str, Any]:
    state = RunState.model_validate(raw)
    response = interrupt({
        "type": "approval_required",
        "run_id": state.run_id,
        "plan": state.plan.model_dump(mode="json") if state.plan else None,
        "gaps": [gap.model_dump(mode="json") for gap in state.gaps],
        "unresolved_critiques": [item.model_dump(mode="json") for item in state.unresolved_critiques],
    })
    decision = str(response.get("decision", "reject")) if isinstance(response, dict) else "reject"
    note = str(response.get("note", "")) if isinstance(response, dict) else ""
    edits = response.get("edits", {}) if isinstance(response, dict) else {}
    if not isinstance(edits, dict):
        edits = {}
    if "weeks" in edits:
        state.weeks = max(1, min(104, int(edits["weeks"])))
    if "hours_per_week" in edits:
        state.hours_per_week = max(0.5, min(100, float(edits["hours_per_week"])))
    state.plan_edits = edits
    if decision == "approve":
        state.approved = True
        state.status = "approved"
    elif decision == "edit":
        state.approved = False
        state.status = "editing"
    else:
        state.approved = False
        state.status = "rejected"
    state.approval_note = note or None
    state.events.append(node_event(state, "human_approval", "node_end", decision=decision, note=note))
    state.traces.append(trace_row(state, "human_approval", metadata={"decision": decision, "note": note}))
    return state.model_dump(mode="python")
