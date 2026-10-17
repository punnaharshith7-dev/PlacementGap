from __future__ import annotations

import operator
import time
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from typing import Annotated, Any, TypedDict, cast

from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.graph import END, START, StateGraph

from agent.contracts import RunState
from agent.nodes.common import trace_row
from agent.nodes.critic import critic_node
from agent.nodes.gap_analysis import gap_analysis_node
from agent.nodes.human_approval import human_approval_node
from agent.nodes.intake import intake_node
from agent.nodes.jd_discovery import jd_discovery_node
from agent.nodes.jd_extract import jd_extract_node
from agent.nodes.plan_build import plan_build_node
from agent.nodes.prioritize import prioritize_node
from agent.nodes.profile_normalize import profile_normalize_node
from agent.nodes.profile_parse import profile_parse_node
from agent.nodes.report import report_node


class AgentState(TypedDict, total=False):
    run_id: str
    student_id: str
    profile_text: str
    profile_filename: str | None
    profile_file_base64: str | None
    jd_text: str
    jd_url: str | None
    role: str
    company: str | None
    weeks: int
    hours_per_week: float
    max_cost_usd: float
    max_tokens: int
    request_id: str | None
    source_doc_id: str
    profile: dict[str, Any] | None
    job: dict[str, Any] | None
    gaps: list[dict[str, Any]]
    plan: dict[str, Any] | None
    critiques: list[dict[str, Any]]
    unresolved_critiques: list[dict[str, Any]]
    critique_iteration: int
    approved: bool
    approval_note: str | None
    plan_edits: dict[str, Any]
    status: str
    degraded: bool
    degraded_reasons: list[str]
    discovery_tier: str
    traces: Annotated[list[dict[str, Any]], operator.add]
    events: Annotated[list[dict[str, Any]], operator.add]
    report_markdown: str | None
    report_json: dict[str, Any] | None
    report_pdf: bytes | None
    budget_snapshot: dict[str, Any]


Node = Callable[[dict[str, Any]], Any]


def _checkpoint_serializer() -> JsonPlusSerializer:
    """Allow only the enum types present in validated run state."""
    return JsonPlusSerializer(allowed_msgpack_modules=[
        ("agent.contracts", "SkillLevel"),
        ("agent.contracts", "GapVerdict"),
    ])


def _boundary(node_name: str, node: Node) -> Callable[[dict[str, Any]], Any]:
    async def validated_node(raw: dict[str, Any]) -> dict[str, Any]:
        started = time.perf_counter()
        before = RunState.model_validate(raw)
        result = await node(raw)
        after = RunState.model_validate(result)
        after.traces.append(trace_row(
            after,
            node_name,
            latency_ms=int((time.perf_counter() - started) * 1000),
            metadata={"boundary_validation": "passed", "node_name": node_name},
        ))
        before_values = before.model_dump(mode="python")
        after_values = after.model_dump(mode="python")
        updates = {
            key: value
            for key, value in after_values.items()
            if key not in {"traces", "events"} and before_values.get(key) != value
        }
        for list_key in ("traces", "events"):
            prior = before_values.get(list_key, [])
            current = after_values.get(list_key, [])
            updates[list_key] = current[len(prior) :] if len(current) >= len(prior) else current
        # Re-validation here ensures no malformed node output can reach a downstream boundary.
        RunState.model_validate({**before_values, **updates})
        return updates

    validated_node.__name__ = node_name
    return validated_node


def _after_critic(state: AgentState) -> str:
    validated = RunState.model_validate(state)
    if validated.critiques and validated.critique_iteration < 2:
        return "plan_build"
    return "human_approval"


def _after_approval(state: AgentState) -> str:
    validated = RunState.model_validate(state)
    if validated.approved:
        return "report"
    if validated.status == "editing":
        return "plan_build"
    return END


def create_graph(checkpointer: Any | None = None, *, skip_critic: bool = False) -> Any:
    graph = StateGraph(AgentState)
    for name, node in (
        ("intake", intake_node),
        ("jd_discovery", jd_discovery_node),
        ("jd_extract", jd_extract_node),
        ("profile_parse", profile_parse_node),
        ("profile_normalize", profile_normalize_node),
        ("gap_analysis", gap_analysis_node),
        ("prioritize", prioritize_node),
        ("plan_build", plan_build_node),
        ("critic", critic_node),
        ("human_approval", human_approval_node),
        ("report", report_node),
    ):
        graph.add_node(name, cast(Any, _boundary(name, node)))
    graph.add_edge(START, "intake")
    graph.add_edge("intake", "jd_discovery")
    graph.add_edge("intake", "profile_parse")
    graph.add_edge("jd_discovery", "jd_extract")
    graph.add_edge("profile_parse", "profile_normalize")
    graph.add_edge(["jd_extract", "profile_normalize"], "gap_analysis")
    graph.add_edge("gap_analysis", "prioritize")
    graph.add_edge("prioritize", "plan_build")
    if skip_critic:
        graph.add_edge("plan_build", "human_approval")
    else:
        graph.add_edge("plan_build", "critic")
        graph.add_conditional_edges("critic", _after_critic, {"plan_build": "plan_build", "human_approval": "human_approval"})
    graph.add_conditional_edges("human_approval", _after_approval, {"report": "report", "plan_build": "plan_build", END: END})
    graph.add_edge("report", END)
    return graph.compile(checkpointer=checkpointer or MemorySaver(serde=_checkpoint_serializer()))


class PostgresCheckpointRuntime:
    """Owns an async PostgresSaver for the lifetime of the API process."""

    def __init__(self, connection_string: str) -> None:
        self.connection_string = connection_string
        self._manager: AbstractAsyncContextManager[Any] | None = None
        self.graph: Any | None = None

    async def start(self) -> None:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

        self._manager = AsyncPostgresSaver.from_conn_string(
            self.connection_string,
            serde=_checkpoint_serializer(),
        )
        saver = await self._manager.__aenter__()
        await saver.setup()
        self.graph = create_graph(saver)

    async def stop(self) -> None:
        if self._manager:
            await self._manager.__aexit__(None, None, None)
            self._manager = None
