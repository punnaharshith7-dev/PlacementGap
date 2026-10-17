from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RunBudget:
    """Hard, deterministic per-run token and spend guard."""

    max_usd: float = 1.0
    max_tokens: int = 40_000
    total_usd: float = 0.0
    total_tokens: int = 0
    node_costs: dict[str, float] = field(default_factory=dict)
    node_tokens: dict[str, int] = field(default_factory=dict)
    degraded: bool = False
    reduction_reason: str | None = None

    @classmethod
    def restore(cls, snapshot: dict[str, object], *, max_usd: float, max_tokens: int) -> RunBudget:
        raw_node_costs = snapshot.get("node_costs")
        raw_node_tokens = snapshot.get("node_tokens")
        node_costs: dict[str, float] = {}
        node_tokens: dict[str, int] = {}
        if isinstance(raw_node_costs, dict):
            node_costs = {
                str(key): float(value)
                for key, value in raw_node_costs.items()
                if isinstance(value, (int, float))
            }
        if isinstance(raw_node_tokens, dict):
            node_tokens = {
                str(key): int(value)
                for key, value in raw_node_tokens.items()
                if isinstance(value, int)
            }
        total_usd = snapshot.get("total_usd", 0.0)
        total_tokens = snapshot.get("total_tokens", 0)
        return cls(
            max_usd=max_usd,
            max_tokens=max_tokens,
            total_usd=float(total_usd) if isinstance(total_usd, (int, float)) else 0.0,
            total_tokens=int(total_tokens) if isinstance(total_tokens, int) else 0,
            node_costs=node_costs,
            node_tokens=node_tokens,
            degraded=bool(snapshot.get("degraded", False)),
            reduction_reason=str(snapshot["reduction_reason"]) if snapshot.get("reduction_reason") else None,
        )

    def can_spend(self, estimated_tokens: int, estimated_usd: float) -> bool:
        allowed = (
            self.total_tokens + estimated_tokens <= self.max_tokens
            and self.total_usd + estimated_usd <= self.max_usd
        )
        if not allowed:
            self.degraded = True
            self.reduction_reason = (
                f"Run budget reached (tokens {self.total_tokens}/{self.max_tokens}, "
                f"USD {self.total_usd:.4f}/{self.max_usd:.4f}); optional model work was skipped."
            )
        return allowed

    def record(
        self, *, node: str, input_tokens: int, output_tokens: int, cost_usd: float
    ) -> None:
        tokens = input_tokens + output_tokens
        self.total_tokens += tokens
        self.total_usd += cost_usd
        self.node_tokens[node] = self.node_tokens.get(node, 0) + tokens
        self.node_costs[node] = self.node_costs.get(node, 0.0) + cost_usd
        if self.total_usd > self.max_usd or self.total_tokens > self.max_tokens:
            self.degraded = True
            self.reduction_reason = "Provider-reported usage crossed the run budget after the call completed."

    def snapshot(self) -> dict[str, object]:
        return {
            "max_usd": self.max_usd,
            "max_tokens": self.max_tokens,
            "total_usd": round(self.total_usd, 6),
            "total_tokens": self.total_tokens,
            "node_costs": dict(self.node_costs),
            "node_tokens": dict(self.node_tokens),
            "degraded": self.degraded,
            "reduction_reason": self.reduction_reason,
        }
