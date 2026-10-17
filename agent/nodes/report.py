from __future__ import annotations

from typing import Any

from agent.contracts import RunState
from agent.nodes.common import node_event, trace_row
from agent.tools.render_report import render_report


async def report_node(raw: dict[str, Any]) -> dict[str, Any]:
    state = RunState.model_validate(raw)
    if not state.approved:
        raise ValueError("Report generation requires human approval")
    rendered = render_report(state)
    state.report_markdown = str(rendered["markdown"])
    state.report_json = rendered["json"]
    state.report_pdf = rendered["pdf"]
    state.status = "completed"
    state.events.append(node_event(state, "report", "node_end", report_ready=True))
    state.traces.append(trace_row(state, "report", metadata={
        "formats": ["markdown", "pdf", "json"],
        "provenance_claims": len(state.report_json.get("provenance", [])),
        "unresolved_critiques": len(state.unresolved_critiques),
        "tools_allowed": ["render_report"],
    }))
    return state.model_dump(mode="python")
