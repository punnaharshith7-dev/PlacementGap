from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from agent.contracts import RunState, TraceRow


def state_from(value: dict[str, Any]) -> RunState:
    return RunState.model_validate(value)


def node_event(state: RunState, node: str, status: str, **payload: Any) -> dict[str, Any]:
    return {
        "run_id": state.run_id,
        "node": node,
        "status": status,
        "timestamp": datetime.now(UTC).isoformat(),
        **payload,
    }


def trace_row(
    state: RunState,
    node: str,
    *,
    call_type: str = "node",
    model: str = "deterministic-python",
    prompt_version: str = "v1",
    latency_ms: int = 0,
    retry_count: int = 0,
    cache_hit: bool = False,
    metadata: dict[str, Any] | None = None,
) -> TraceRow:
    return TraceRow(
        run_id=state.run_id,
        node_name=node,
        call_type=call_type,
        model=model,
        prompt_version=prompt_version,
        latency_ms=latency_ms,
        retry_count=retry_count,
        cache_hit=cache_hit,
        timestamp=datetime.now(UTC).isoformat(),
        metadata=metadata or {},
    )


def tool_trace(state: RunState, node: str, payload: dict[str, Any]) -> None:
    state.traces.append(trace_row(
        state,
        node,
        call_type="tool",
        model=str(payload.get("tool", "tool")),
        latency_ms=int(payload.get("latency_ms", 0)),
        retry_count=max(0, int(payload.get("attempts", 1)) - 1),
        cache_hit=bool(payload.get("cache_hit", False)),
        metadata=payload,
    ))
