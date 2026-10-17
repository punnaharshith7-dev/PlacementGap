from __future__ import annotations

import argparse
import asyncio
import json
import random
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from agent.tools.base import execute_tool

FAILURE_TYPES = ("timeout", "http_5xx", "malformed_json", "empty_result", "truncated_response", "rate_limit")


async def run_chaos(rate: float, samples: int = 30, seed: int = 2701) -> dict[str, Any]:
    rng = random.Random(seed)
    report: dict[str, Any] = {}
    for failure_type in FAILURE_TYPES:
        injected = 0
        recovered = 0
        attempts: list[int] = []
        for sample in range(samples):
            should_inject = rng.random() < rate
            if should_inject:
                injected += 1
            calls = 0

            async def fake_tool(
                bound_failure_type: str = failure_type,
                inject: bool = should_inject,
            ) -> dict[str, str]:
                nonlocal calls
                calls += 1
                fail = inject and calls == 1
                if fail:
                    if bound_failure_type == "timeout":
                        await asyncio.sleep(0.04)
                    elif bound_failure_type == "http_5xx":
                        raise RuntimeError("HTTP 503 fixture failure")
                    elif bound_failure_type == "malformed_json":
                        raise ValueError("Fixture JSON failed schema validation")
                    elif bound_failure_type == "empty_result":
                        raise ValueError("Fixture result set was unexpectedly empty")
                    elif bound_failure_type == "truncated_response":
                        raise ValueError("Fixture response was truncated before closing token")
                    elif bound_failure_type == "rate_limit":
                        raise RuntimeError("HTTP 429 fixture rate-limit")
                return {"status": "ok"}

            result = await execute_tool(
                name=f"chaos_{failure_type}_{sample}",
                call=fake_tool,
                timeout_s=0.015,
                max_attempts=3,
            )
            attempts.append(result.attempts)
            if should_inject and result.status == "ok" and result.attempts > 1:
                recovered += 1
        report[failure_type] = {
            "injected": injected,
            "recovered": recovered,
            "recovery_rate": recovered / injected if injected else 1.0,
            "mean_attempts": sum(attempts) / len(attempts) if attempts else 0,
        }
    result = {
        "generated_at": datetime.now(UTC).isoformat(),
        "seed": seed,
        "chaos_rate": rate,
        "samples_per_failure_type": samples,
        "recovery_by_failure_type": report,
        "injection_resistance_rate": None,
        "note": "Tool-level deterministic transient failures are injected into fixture calls; adversarial prompt injection is measured by evals.runner --adversarial.",
    }
    path = Path("evals/reports")
    path.mkdir(parents=True, exist_ok=True)
    output = path / f"chaos-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    print(f"Wrote {output}")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--chaos-rate", type=float, default=0.3)
    parser.add_argument("--samples", type=int, default=30)
    args = parser.parse_args()
    if not 0 <= args.chaos_rate <= 1:
        raise SystemExit("--chaos-rate must be between 0 and 1")
    asyncio.run(run_chaos(args.chaos_rate, args.samples))


if __name__ == "__main__":
    main()
