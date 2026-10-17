from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DATA = Path(__file__).parent / "datasets" / "judge_calibration.json"


def cohen_kappa(reference: list[bool], judge: list[bool]) -> float:
    if len(reference) != len(judge) or not reference:
        return 0.0
    n = len(reference)
    observed = sum(left == right for left, right in zip(reference, judge, strict=True)) / n
    ref_yes = sum(reference) / n
    judge_yes = sum(judge) / n
    expected = ref_yes * judge_yes + (1 - ref_yes) * (1 - judge_yes)
    return (observed - expected) / (1 - expected) if expected < 1 else 1.0


def main() -> int:
    payload: dict[str, Any] = json.loads(DATA.read_text(encoding="utf-8"))
    rows = payload["labels"]
    if len(rows) < 50:
        raise SystemExit(f"Need 50 calibration labels; found {len(rows)}")
    reports: dict[str, float] = {}
    for judge in ("success", "groundedness"):
        kappa = cohen_kappa(
            [bool(row[judge]["reference"]) for row in rows],
            [bool(row[judge]["judge"]) for row in rows],
        )
        reports[judge] = kappa
        print(f"{judge} Cohen's kappa: {kappa:.3f} ({len(rows)} reference labels)")
        if kappa < 0.6:
            print(f"CI failed: revise evals/judges/{judge}.v1.md and recalibrate the judge.")
    print(f"Reference source: {payload['provenance']}")
    return 0 if all(value >= 0.6 for value in reports.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
