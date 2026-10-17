from __future__ import annotations

import asyncio
import random
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict

from agent.observability import span_for

T = TypeVar("T")


class ToolResult(BaseModel, Generic[T]):
    model_config = ConfigDict(extra="forbid")
    status: Literal["ok", "degraded", "failed"]
    data: T | None = None
    reason: str | None = None
    latency_ms: int = 0
    attempts: int = 1
    cache_hit: bool = False


class CircuitBreaker:
    def __init__(self, threshold: int = 5, reset_seconds: float = 60.0) -> None:
        self.threshold = threshold
        self.reset_seconds = reset_seconds
        self.failures = 0
        self.opened_at: float | None = None
        self._half_open_in_flight = False

    def allow(self) -> bool:
        if self.opened_at is None:
            return True
        if time.monotonic() - self.opened_at >= self.reset_seconds:
            if self._half_open_in_flight:
                return False
            self._half_open_in_flight = True
            return True
        return False

    def success(self) -> None:
        self.failures = 0
        self.opened_at = None
        self._half_open_in_flight = False

    def failure(self) -> None:
        self.failures += 1
        self._half_open_in_flight = False
        if self.failures >= self.threshold:
            self.opened_at = time.monotonic()


_BREAKERS: dict[str, CircuitBreaker] = {}


async def execute_tool(
    *,
    name: str,
    call: Callable[[], Awaitable[T]],
    timeout_s: float = 15.0,
    max_attempts: int = 3,
    trace: Callable[[dict[str, Any]], None] | None = None,
) -> ToolResult[T]:
    breaker = _BREAKERS.setdefault(name, CircuitBreaker())
    started = time.perf_counter()
    if not breaker.allow():
        if trace:
            trace({
                "tool": name,
                "status": "degraded",
                "reason": "circuit_open",
                "attempts": 0,
                "latency_ms": 0,
                "cache_hit": False,
                "timestamp": datetime.now(UTC).isoformat(),
            })
        return ToolResult(
            status="degraded",
            reason=f"{name} circuit is open; retry after the recovery window.",
            latency_ms=0,
            attempts=0,
        )
    error = "unknown tool failure"
    attempts = 0
    for attempts in range(1, max_attempts + 1):
        try:
            with span_for(f"tool.{name}", {"tool.name": name, "tool.attempt": attempts}):
                data = await asyncio.wait_for(call(), timeout=timeout_s)
            breaker.success()
            latency = int((time.perf_counter() - started) * 1000)
            cache_hit = bool(getattr(data, "cache_hit", False))
            if trace:
                trace({
                    "tool": name,
                    "status": "ok",
                    "attempts": attempts,
                    "latency_ms": latency,
                    "cache_hit": cache_hit,
                    "timestamp": datetime.now(UTC).isoformat(),
                })
            return ToolResult(status="ok", data=data, latency_ms=latency, attempts=attempts, cache_hit=cache_hit)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - tool errors become typed results at this boundary
            error = f"{type(exc).__name__}: {exc}"
            if attempts < max_attempts:
                await asyncio.sleep(min(0.25 * 2 ** (attempts - 1) + random.random() * 0.1, 2.0))
    breaker.failure()
    latency = int((time.perf_counter() - started) * 1000)
    if trace:
        trace({
            "tool": name,
            "status": "failed",
            "reason": error,
            "attempts": attempts,
            "latency_ms": latency,
            "cache_hit": False,
            "timestamp": datetime.now(UTC).isoformat(),
        })
    return ToolResult(status="failed", reason=error, latency_ms=latency, attempts=attempts)
