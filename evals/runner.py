from __future__ import annotations

import argparse
import asyncio
import json
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from langgraph.types import Command

from agent.contracts import RunState
from agent.graph import create_graph
from evals.metrics.component import (
    canonicalization_metrics,
    extraction_metrics,
    gap_metrics,
    resource_metrics,
)
from evals.metrics.e2e import end_to_end_metrics
from evals.metrics.ops import ops_metrics
from evals.metrics.trajectory import trajectory_metrics

ROOT = Path(__file__).parent
DATASET = ROOT / "datasets" / "placementgap_100.json"


async def _execute(case: dict[str, Any], graph: Any, *, text_override: str | None = None) -> RunState:
    profile_text = str(case["profile"]["text"])
    job = case["job"]
    run_id = f"eval-{case['case_id']}-{uuid.uuid4().hex[:8]}"
    state = RunState(
        run_id=run_id,
        student_id=str(case["profile"]["student_id"]),
        profile_text=profile_text,
        jd_text=text_override if text_override is not None else str(job["text"]),
        role=str(job["role"]),
        company=str(job["company"]),
        weeks=int(case["weeks"]),
        hours_per_week=float(case["hours_per_week"]),
        source_doc_id=f"profile:{case['profile']['student_id']}",
        max_cost_usd=0.2,
        max_tokens=10_000,
    )
    config = {"configurable": {"thread_id": run_id, "run_id": run_id}}
    result = await graph.ainvoke(state.model_dump(mode="python"), config=config)
    snapshot = await graph.aget_state(config)
    if snapshot and snapshot.tasks and any(getattr(task, "interrupts", ()) for task in snapshot.tasks):
        result = await graph.ainvoke(Command(resume={"decision": "approve", "note": "Fixture evaluation approval."}), config=config)
    return RunState.model_validate(result)


async def run(split: str, *, confirm: bool = False, ablation_variant: str = "full") -> dict[str, Any]:
    if split == "heldout" and not confirm:
        raise SystemExit("Heldout data is frozen. Rerun with both --heldout and --confirm after finalizing changes.")
    os.environ["PLACEMENTGAP_FIXTURES"] = "1"
    os.environ["PLACEMENTGAP_USE_LLM"] = "0"
    os.environ["PLACEMENTGAP_ABLATION"] = ablation_variant
    os.environ["PLACEMENTGAP_SQLITE_PATH"] = f"./data/eval-v2-{split}-{ablation_variant}.sqlite3"
    dataset = json.loads(DATASET.read_text(encoding="utf-8"))
    cases = [case for case in dataset["cases"] if case["split"] == split]
    graph = create_graph(skip_critic=ablation_variant == "no_critic")
    states: list[RunState] = []
    injections: dict[str, bool] = {}
    resources: list[dict[str, Any]] = []
    for index, case in enumerate(cases, 1):
        state = await _execute(case, graph)
        states.append(state)
        if state.plan:
            for week in state.plan.weeks:
                for item in week.items:
                    resources.append({"skill_id": item.skill_id, "resources": [row.model_dump(mode="json") for row in item.resources]})
        if case["job"].get("injection"):
            clean = await _execute(case, graph, text_override=str(case["job"]["clean_text"]))
            injected_verdicts = {gap.skill_id: gap.verdict.value for gap in state.gaps}
            clean_verdicts = {gap.skill_id: gap.verdict.value for gap in clean.gaps}
            injections[str(case["case_id"])] = injected_verdicts == clean_verdicts
        if index % 10 == 0:
            print(f"{split}: {index}/{len(cases)} cases")
    prediction_rows = [
        [requirement.model_dump(mode="json") for requirement in (state.job.requirements if state.job else [])]
        for state in states
    ]
    extraction = [extraction_metrics(predicted, case["labels"]["requirements"]) for predicted, case in zip(prediction_rows, cases, strict=True)]
    extraction_report = {
        label: {
            metric: sum(row[label][metric] for row in extraction) / len(extraction) if extraction else 0.0
            for metric in ("precision", "recall", "f1")
        }
        for label in ("hard", "preferred")
    }
    canonical_file = __import__("yaml").safe_load((ROOT.parent / "ontology" / "data" / "alias_tests.yaml").read_text(encoding="utf-8"))
    canonical_report = canonicalization_metrics(canonical_file["cases"])
    gap_rows = []
    for case, state in zip(cases, states, strict=True):
        predicted = {gap.skill_id: gap.verdict.value for gap in state.gaps}
        expected = case["labels"].get("expected_gaps", {})
        gap_rows.append(gap_metrics(predicted, expected))
    classes = ["has", "partial", "missing"]
    confusion = {gold: {guess: 0 for guess in classes} for gold in classes}
    for row in gap_rows:
        for gold in classes:
            for guess in classes:
                confusion[gold][guess] += row["confusion_matrix"][gold][guess]
    gap_report = gap_metrics(
        {f"{index}-{skill}": verdict for index, state in enumerate(states) for skill, verdict in {item.skill_id: item.verdict.value for item in state.gaps}.items()},
        {f"{index}-{skill}": verdict for index, case in enumerate(cases) for skill, verdict in case["labels"].get("expected_gaps", {}).items()},
    )
    gap_report["confusion_matrix"] = confusion
    e2e = end_to_end_metrics(cases, states)
    ops = ops_metrics(states)
    trajectory = trajectory_metrics(states, injections if split == "adversarial" else None)
    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "split": split,
        "ablation_variant": ablation_variant,
        "case_count": len(cases),
        "dataset_seed": dataset["seed"],
        "fixture_mode": True,
        "metrics": {
            "component": {
                "skill_extraction": extraction_report,
                "canonicalization": canonical_report,
                "gap_classification": gap_report,
                "resource_quality": resource_metrics(resources),
            },
            "end_to_end": e2e,
            "trajectory": trajectory,
            "ops": ops,
        },
        "case_results": [
            {
                "case_id": case["case_id"],
                "status": state.status,
                "discovery_tier": state.discovery_tier,
                "gaps": {gap.skill_id: gap.verdict.value for gap in state.gaps},
                "plan_validity": bool(state.plan and not state.plan.violations),
                "cost_usd": sum(row.cost_usd for row in state.traces),
                "latency_ms": sum(row.latency_ms for row in state.traces),
            }
            for case, state in zip(cases, states, strict=True)
        ],
        "limitations": [
            "Task-success judge uses deterministic fixture checks because live LLM judging is disabled.",
            "Resource link checks are limited to the offline fixture catalog; unlisted URLs are unverified.",
            "Seeded calibration labels are not a substitute for a blinded human study.",
        ],
    }
    report_dir = ROOT / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = report_dir / f"{split}-{timestamp}.json"
    report["report_path"] = path.as_posix()
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {path}")
    print(json.dumps({"plan_validity": e2e["plan_validity"], "skill_extraction": extraction_report, "canonicalization": canonical_report["accuracy"]}, indent=2))
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--heldout", action="store_true")
    parser.add_argument("--confirm", action="store_true")
    parser.add_argument("--adversarial", action="store_true")
    args = parser.parse_args()
    split = "heldout" if args.heldout else "adversarial" if args.adversarial else "dev"
    asyncio.run(run(split, confirm=args.confirm))


if __name__ == "__main__":
    main()
