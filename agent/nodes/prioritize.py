from __future__ import annotations

from typing import Any

from agent.contracts import RunState
from agent.nodes.common import node_event, trace_row
from agent.scoring import score_gaps


async def prioritize_node(raw: dict[str, Any]) -> dict[str, Any]:
    state = RunState.model_validate(raw)
    result = score_gaps(state.gaps)
    state.gaps = result.gaps
    state.events.append(node_event(state, "prioritize", "node_end", weight_table=result.weight_table))
    state.traces.append(trace_row(
        state,
        "prioritize",
        metadata={"weight_table": result.weight_table, "ordered_skill_ids": [gap.skill_id for gap in result.gaps]},
    ))
    return state.model_dump(mode="python")
