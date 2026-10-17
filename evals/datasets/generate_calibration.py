from __future__ import annotations

import json
from pathlib import Path


def main() -> None:
    rows = []
    for index in range(50):
        success_reference = index % 3 != 0
        grounded_reference = index % 4 != 0
        rows.append({
            "case_id": f"judge-cal-{index + 1:02d}",
            "success": {"reference": success_reference, "judge": not success_reference if index % 8 == 0 else success_reference},
            "groundedness": {"reference": grounded_reference, "judge": not grounded_reference if index % 10 == 0 else grounded_reference},
        })
    payload = {
        "provenance": "synthetic seeded reference labels for offline bootstrap; replace with blinded human labels before claiming human calibration",
        "rubric_versions": {"success": "success.v1", "groundedness": "groundedness.v1"},
        "labels": rows,
    }
    output = Path(__file__).parent / "judge_calibration.json"
    output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {len(rows)} deterministic offline reference labels to {output}")


if __name__ == "__main__":
    main()
