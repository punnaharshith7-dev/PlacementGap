from __future__ import annotations

from pathlib import Path

import yaml

from evals.metrics.component import canonicalization_metrics

ROOT = Path(__file__).parent.parent


def main() -> int:
    data = yaml.safe_load((ROOT / "ontology" / "data" / "alias_tests.yaml").read_text(encoding="utf-8"))
    report = canonicalization_metrics(data["cases"])
    print(f"alias accuracy: {report['accuracy']:.3f} over {report['case_count']} labels")
    for method, metrics in report["by_method"].items():
        print(f"  {method}: {metrics['correct']}/{metrics['total']} = {metrics['accuracy']:.3f}")
    print(f"unresolved rate: {report['unresolved_rate']:.3f}")
    return 0 if report["accuracy"] >= 0.95 else 1


if __name__ == "__main__":
    raise SystemExit(main())
