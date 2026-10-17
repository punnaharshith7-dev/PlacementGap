from __future__ import annotations

import asyncio
from typing import Any

from agent.contracts import JobDescription
from agent.nodes.common import node_event, state_from, tool_trace, trace_row
from agent.tools.base import execute_tool
from agent.tools.fetch_url import fetch_url
from agent.tools.search_jds import search_jds
from memory.semantic_cache import content_hash


def _archetype(role: str) -> str:
    return (
        f"Role archetype for {role}. Candidates should use the role's core programming language, "
        "data structures and algorithms, version control, automated testing, API design, "
        "database fundamentals, and clear technical communication."
    )


async def jd_discovery_node(raw: dict[str, Any]) -> dict[str, Any]:
    state = state_from(raw)
    text = state.jd_text.strip()
    tier = "provided_text"
    source_id = "jd:pasted"
    digest = content_hash(text) if text else ""
    if state.jd_url:
        fetched = await execute_tool(
            name="fetch_url",
            call=lambda: fetch_url(state.jd_url or ""),
            timeout_s=15,
            trace=lambda row: tool_trace(state, "jd_discovery", {**row, "url": state.jd_url}),
        )
        if fetched.status == "ok" and fetched.data:
            text = fetched.data.text
            digest = fetched.data.content_hash
            source_id = f"jd:url:{digest[:16]}"
            tier = "live_url"
        else:
            state.degraded = True
            state.degraded_reasons.append(f"Live JD fetch failed: {fetched.reason or fetched.status}.")
            text = ""
    if not text:
        search = await execute_tool(
            name="search_jds",
            call=lambda: _search_async(state.role or "software engineer", state.company),
            timeout_s=3,
            trace=lambda row: tool_trace(state, "jd_discovery", {
                **row, "role": state.role or "software engineer", "company": state.company,
            }),
        )
        if search.status == "ok" and search.data:
            chosen = search.data[0]
            text = chosen.text
            digest = content_hash(text)
            source_id = f"jd:fixture:{digest[:16]}"
            tier = "similar_jd_same_role"
            state.role = state.role or chosen.role
            state.company = state.company or chosen.company
        else:
            text = _archetype(state.role or "Software Engineer")
            digest = content_hash(text)
            source_id = f"jd:archetype:{digest[:16]}"
            tier = "role_archetype"
            state.degraded = True
            state.degraded_reasons.append("No JD text, fetchable URL, or same-role fixture was available; role archetype used.")
    state.discovery_tier = tier
    state.job = JobDescription(
        source_doc_id=source_id,
        role=state.role or "Software Engineer",
        company=state.company,
        text=text,
        discovery_tier=tier,
        content_hash=digest,
        degraded=tier == "role_archetype",
        degraded_reason="Role archetype fallback used." if tier == "role_archetype" else None,
    )
    state.events.append(node_event(state, "jd_discovery", "node_end", tier=tier, source_doc_id=source_id))
    state.traces.append(trace_row(state, "jd_discovery", metadata={"tier": tier, "source_doc_id": source_id, "tools_allowed": ["fetch_url", "search_jds"]}))
    return state.model_dump(mode="python")


async def _search_async(role: str, company: str | None) -> Any:
    return await asyncio.to_thread(search_jds, role=role, company=company, n=3)
