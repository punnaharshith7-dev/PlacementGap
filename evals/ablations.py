from __future__ import annotations

import argparse
import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from evals.runner import run

START = "<!-- ABLATION_TABLE_START -->"
END = "<!-- ABLATION_TABLE_END -->"
VARIANTS = [
    "full",
    "single_prompt_baseline",
    "no_ontology",
    "no_critic",
    "no_memory",
    "cheap_model_only",
    "no_deterministic_solver",
]
FIXTURE_VARIANTS = {"full", "no_ontology", "no_critic", "no_memory"}
MODEL_VARIANTS = set(VARIANTS) - FIXTURE_VARIANTS


def _table(results: dict[str, dict[str, Any]]) -> str:
    lines = [
        "| Variant | Success rate | Plan validity | Cost / run (USD) | p95 latency (ms) |",
        "|---|---:|---:|---:|---:|",
    ]
    for name in VARIANTS:
        result = results[name]
        if result["status"] != "measured":
            cells = ["N/A"] * 4
        else:
            metrics = result["report"]["metrics"]
            success = metrics["end_to_end"]["task_success_rate"]
            validity = metrics["end_to_end"]["plan_validity"]["pass_rate"]
            cost = metrics["ops"]["cost_usd"]["p50"]
            latency = metrics["ops"]["latency_ms"]["p95"]
            cells = [f"{success:.1%}", f"{validity:.1%}", f"${cost:.4f}", f"{latency:.0f}"]
        lines.append(f"| {name} | " + " | ".join(cells) + " |")
    return "\n".join(lines)


async def main_async(heldout: bool, confirm: bool) -> None:
    if not heldout or not confirm:
        raise SystemExit("Ablations use the frozen heldout split. Pass --heldout --confirm to run.")
    results: dict[str, dict[str, Any]] = {}
    for variant in VARIANTS:
        if variant in MODEL_VARIANTS:
            results[variant] = {
                "status": "not_measured",
                "reason": "This fixture run disables model calls, so the model-specific variant cannot be measured.",
            }
            continue
        report = await run("heldout", confirm=True, ablation_variant=variant)
        results[variant] = {"status": "measured", "report": report}

    table = _table(results)
    timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    report_path = Path("evals/reports") / f"ablation-{timestamp}.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps({
        "generated_at": datetime.now(UTC).isoformat(),
        "split": "heldout",
        "variants": {
            name: ({"status": result["status"], "reason": result["reason"]}
                   if result["status"] != "measured" else {
                       "status": "measured",
                       "report_file": result["report"]["report_path"],
                       "metrics": result["report"]["metrics"],
                   })
            for name, result in results.items()
        },
        "table": table,
    }, indent=2, ensure_ascii=False), encoding="utf-8")

    readme_path = Path("README.md")
    readme = readme_path.read_text(encoding="utf-8")
    if START not in readme or END not in readme:
        raise SystemExit("README.md must contain the ablation table markers")
    left, remainder = readme.split(START, 1)
    _, right = remainder.split(END, 1)
    replacement = (
        f"{START}\n\n{table}\n\n"
        "Measured rows were run independently on the frozen fixture split. `N/A` rows require a recorded or live model provider and are never filled with estimated multipliers. "
        f"The full per-variant report is `{report_path.as_posix()}`.\n\n{END}"
    )
    readme_path.write_text(left + replacement + right, encoding="utf-8")
    print(table)
    print(f"Wrote {report_path} and updated README.md")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--heldout", action="store_true")
    parser.add_argument("--confirm", action="store_true")
    args = parser.parse_args()
    asyncio.run(main_async(args.heldout, args.confirm))


if __name__ == "__main__":
    main()
