from __future__ import annotations

import argparse
import json
from pathlib import Path

DATA = Path(__file__).parent / "datasets" / "placementgap_100.json"


def main() -> None:
    parser = argparse.ArgumentParser(description="Edit a label in the PlacementGap 100-pair dataset")
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--skill-id", required=True)
    parser.add_argument("--verdict", choices=("has", "partial", "missing"), required=True)
    parser.add_argument("--requirement", choices=("hard", "preferred"))
    args = parser.parse_args()
    payload = json.loads(DATA.read_text(encoding="utf-8"))
    case = next((row for row in payload["cases"] if row["case_id"] == args.case_id), None)
    if case is None:
        raise SystemExit(f"Unknown case id: {args.case_id}")
    if case["split"] == "heldout":
        raise SystemExit("Heldout labels are frozen; edit dev labels only.")
    case["labels"].setdefault("expected_gaps", {})[args.skill_id] = args.verdict
    if args.requirement:
        for row in case["labels"].setdefault("requirements", []):
            if row["skill_id"] == args.skill_id:
                row["hard_requirement"] = args.requirement == "hard"
                break
        else:
            case["labels"]["requirements"].append({"skill_id": args.skill_id, "hard_requirement": args.requirement == "hard"})
    DATA.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Updated {args.case_id}: {args.skill_id} -> {args.verdict}")


if __name__ == "__main__":
    main()
