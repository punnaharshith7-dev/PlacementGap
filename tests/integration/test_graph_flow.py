from __future__ import annotations

import pytest
from langgraph.types import Command

from agent.contracts import RunState
from agent.graph import create_graph


@pytest.mark.asyncio
async def test_full_graph_pauses_for_approval_and_emits_pdf(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("PLACEMENTGAP_SQLITE_PATH", str(tmp_path / "profiles.sqlite3"))
    monkeypatch.setenv("PLACEMENTGAP_USE_LLM", "0")
    graph = create_graph()
    state = RunState(
        run_id="integration-run",
        student_id="integration-student",
        profile_text="B.Tech Computer Science\nCoursework: Python, Data Structures, Statistics\nProjects:\nBuilt a REST API using Python and PostgreSQL.",
        jd_text="Software Engineer requires Python, PostgreSQL, REST APIs, Docker, and Unit Testing. React is preferred.",
        role="Software Engineer",
        weeks=8,
        hours_per_week=8,
        source_doc_id="profile:integration-student",
    )
    config = {"configurable": {"thread_id": state.run_id}}
    first = await graph.ainvoke(state.model_dump(mode="python"), config=config)
    snapshot = await graph.aget_state(config)
    assert snapshot is not None
    assert any(getattr(task, "interrupts", ()) for task in snapshot.tasks)
    assert not first.get("approved", False)

    final = await graph.ainvoke(Command(resume={"decision": "approve"}), config=config)
    result = RunState.model_validate(final)
    assert result.status == "completed"
    assert result.plan is not None
    assert result.report_markdown
    assert result.report_json is not None
    assert result.report_pdf and result.report_pdf.startswith(b"%PDF")
    assert all(gap.skill_id for gap in result.gaps)
