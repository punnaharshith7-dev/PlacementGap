from __future__ import annotations

import json
from collections import Counter
from typing import Any

from agent.contracts import RunState


def trajectory_metrics(states: list[RunState], injections: dict[str, bool] | None = None) -> dict[str, Any]:
    calls = 0
    influenced = 0
    steps: list[int] = []
    redundant_calls = 0
    critic_used = 0
    for state in states:
        tool_rows = [row for row in state.traces if row.call_type == "tool"]
        calls += len(tool_rows)
        influenced += sum(
            row.metadata.get("status") == "ok"
            and row.model in {"search_jds", "fetch_url", "parse_document", "find_resources"}
            or row.cache_hit
            for row in tool_rows
        )
        calls_in_state = Counter(
            json.dumps(
                {
                    "node": row.node_name,
                    "tool": row.model,
                    "arguments": {
                        key: value
                        for key, value in row.metadata.items()
                        if key in {"skill_id", "url", "role", "company", "content_hash", "query"}
                    },
                },
                sort_keys=True,
            )
            for row in tool_rows
        )
        redundant_calls += sum(count - 1 for count in calls_in_state.values() if count > 1)
        steps.append(len({row.node_name for row in state.traces}))
        critic_used += int(state.critique_iteration > 1)
    return {
        "tool_call_precision": influenced / calls if calls else 1.0,
        "tool_calls": calls,
        "mean_steps_to_completion": sum(steps) / len(steps) if steps else 0.0,
        "redundant_call_rate": redundant_calls / calls if calls else 0.0,
        "critic_loop_utilization": critic_used / len(states) if states else 0.0,
        "recovery_by_failure_type": {},
        "injection_resistance_rate": None if not injections else sum(injections.values()) / len(injections),
        "injected_runs": len(injections or {}),
    }
