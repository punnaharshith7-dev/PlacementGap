from __future__ import annotations

from agent.contracts import RunState, TraceRow
from evals.metrics.trajectory import trajectory_metrics


def _state(
    run_id: str, *, model: str, status: str, skill_id: str = "python", duplicate: bool = False
) -> RunState:
    row = TraceRow(
        run_id=run_id,
        node_name="plan_build",
        call_type="tool",
        model=model,
        prompt_version="v1",
        timestamp="2026-10-17T00:00:00+00:00",
        metadata={"status": status, "skill_id": skill_id},
    )
    traces = [row, row.model_copy(update={"timestamp": "2026-10-17T00:00:01+00:00"})] if duplicate else [row]
    return RunState(run_id=run_id, student_id=run_id, profile_text="", traces=traces)


def test_trajectory_metrics_scope_redundancy_to_a_single_run() -> None:
    across_runs = trajectory_metrics([
        _state("one", model="find_resources", status="ok"),
        _state("two", model="find_resources", status="ok"),
    ])
    assert across_runs["redundant_call_rate"] == 0
    assert across_runs["tool_call_precision"] == 1

    within_run = trajectory_metrics([_state("three", model="find_resources", status="ok", duplicate=True)])
    assert within_run["redundant_call_rate"] == 0.5

    first_resource = _state("four", model="find_resources", status="ok")
    second_resource = first_resource.traces[0].model_copy(update={"metadata": {"status": "ok", "skill_id": "react"}})
    distinct_arguments = trajectory_metrics([first_resource.model_copy(update={"traces": [first_resource.traces[0], second_resource]})])
    assert distinct_arguments["redundant_call_rate"] == 0
