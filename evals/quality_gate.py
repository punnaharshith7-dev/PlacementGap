from __future__ import annotations

import json
import sys
from pathlib import Path

reports = sorted(Path("evals/reports").glob("dev-*.json"), key=lambda path: path.stat().st_mtime, reverse=True)
if not reports:
    raise SystemExit("No dev evaluation report found; run evals.runner first.")
baseline = json.loads(Path("evals/baseline.json").read_text(encoding="utf-8"))
current = json.loads(reports[0].read_text(encoding="utf-8"))
success = current["metrics"]["end_to_end"]["task_success_rate"]
validity = current["metrics"]["end_to_end"]["plan_validity"]["pass_rate"]
cost = current["metrics"]["ops"]["cost_usd"]["p50"]
success_floor = float(baseline["task_success_rate"]) - 0.03
cost_ceiling = float(baseline["cost_per_run_usd"]) * 1.15
failures = []
if success < success_floor:
    failures.append(f"success rate {success:.3f} is below baseline floor {success_floor:.3f}")
if cost > cost_ceiling:
    failures.append(f"cost/run ${cost:.5f} exceeds baseline ceiling ${cost_ceiling:.5f}")
print(f"quality gate: success={success:.3f}, plan_validity={validity:.3f}, cost/run=${cost:.5f}")
if failures:
    print("\n".join(f"FAIL: {failure}" for failure in failures))
    sys.exit(1)
print("quality gate passed")
