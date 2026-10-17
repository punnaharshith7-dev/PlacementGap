from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

from langgraph.types import Command

from agent.contracts import RunState
from agent.graph import create_graph


async def main() -> None:
    os.environ.setdefault("PLACEMENTGAP_FIXTURES", "1")
    os.environ.setdefault("PLACEMENTGAP_USE_LLM", "0")
    state = RunState(
        run_id="placementgap-demo",
        student_id="placementgap-demo",
        profile_text=(
            "B.Tech Computer Science, CGPA 8.4\n"
            "Coursework: Python, Data Structures, Algorithms, Statistics, Databases\n"
            "Projects:\nBuilt and deployed a REST API using Python and PostgreSQL.\n"
            "Software Engineering Intern — implemented automated tests and Docker deployment."
        ),
        jd_text=(
            "Software Engineer requirements: Python, Data Structures and Algorithms, REST APIs, "
            "PostgreSQL, Docker, Unit Testing, Git, and React. Candidates should build reliable APIs; "
            "Kubernetes is preferred."
        ),
        role="Software Engineer",
        company="Northstar Labs",
        weeks=8,
        hours_per_week=8,
        source_doc_id="profile:placementgap-demo",
    )
    graph = create_graph()
    config = {"configurable": {"thread_id": state.run_id, "run_id": state.run_id}}
    first = await graph.ainvoke(state.model_dump(mode="python"), config=config)
    snapshot = await graph.aget_state(config)
    if snapshot and snapshot.tasks and any(getattr(task, "interrupts", ()) for task in snapshot.tasks):
        resumed = await graph.ainvoke(Command(resume={"decision": "approve"}), config=config)
        final = RunState.model_validate(resumed)
    else:
        final = RunState.model_validate(first)
    if final.status != "completed" or not final.report_pdf:
        raise RuntimeError(f"Demo did not complete report generation (status={final.status})")
    output_dir = Path("data/demo")
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "report.pdf").write_bytes(final.report_pdf)
    (output_dir / "report.md").write_text(final.report_markdown or "", encoding="utf-8")
    (output_dir / "report.json").write_text(json.dumps(final.report_json, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Completed fixture run {final.run_id}; PDF: {output_dir / 'report.pdf'}")
    print(f"Discovery tier: {final.discovery_tier}; gaps: {len(final.gaps)}; scheduled: {final.plan.total_hours if final.plan else 0:g}h")


if __name__ == "__main__":
    asyncio.run(main())
