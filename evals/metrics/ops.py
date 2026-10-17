from __future__ import annotations

from statistics import median

from agent.contracts import RunState


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int((len(ordered) - 1) * pct)))
    return ordered[index]


def ops_metrics(states: list[RunState]) -> dict[str, object]:
    costs: list[float] = []
    latencies: list[float] = []
    node_costs: dict[str, float] = {}
    node_latencies: dict[str, list[float]] = {}
    waterfalls: dict[str, list[float]] = {}
    total_calls = 0
    cache_hits = 0
    usd_saved = 0.0
    for state in states:
        cost = sum(row.cost_usd for row in state.traces)
        costs.append(cost)
        total_calls += sum(row.call_type in {"tool", "llm"} for row in state.traces)
        cache_hits += sum(row.call_type in {"tool", "llm"} and row.cache_hit for row in state.traces)
        usd_saved += sum(float(row.metadata.get("usd_saved", 0)) for row in state.traces)
        node_durations: dict[str, float] = {}
        for row in state.traces:
            node_costs[row.node_name] = node_costs.get(row.node_name, 0.0) + row.cost_usd
            if row.call_type == "node":
                node_latencies.setdefault(row.node_name, []).append(float(row.latency_ms))
                node_durations[row.node_name] = node_durations.get(row.node_name, 0.0) + row.latency_ms
        jd_branch = node_durations.get("jd_discovery", 0.0) + node_durations.get("jd_extract", 0.0)
        profile_branch = node_durations.get("profile_parse", 0.0) + node_durations.get("profile_normalize", 0.0)
        waterfall = {
            "intake": node_durations.get("intake", 0.0),
            "parallel_ingestion": max(jd_branch, profile_branch),
            "gap_analysis": node_durations.get("gap_analysis", 0.0),
            "prioritize": node_durations.get("prioritize", 0.0),
            "plan_build": node_durations.get("plan_build", 0.0),
            "critic": node_durations.get("critic", 0.0),
            "human_approval": node_durations.get("human_approval", 0.0),
            "report": node_durations.get("report", 0.0),
        }
        latencies.append(sum(waterfall.values()))
        for node, duration in waterfall.items():
            waterfalls.setdefault(node, []).append(duration)
    profile_cost = lambda state: sum(
        row.cost_usd for row in state.traces if row.node_name in {"profile_parse", "profile_normalize"}
    )
    profile_cold_costs = [
        profile_cost(state)
        for state in states
        if not next((bool(row.metadata.get("warm_profile")) for row in state.traces if row.node_name == "intake"), False)
    ]
    profile_warm_costs = [
        profile_cost(state)
        for state in states
        if next((bool(row.metadata.get("warm_profile")) for row in state.traces if row.node_name == "intake"), False)
    ]
    return {
        "cost_usd": {"p50": median(costs) if costs else 0, "p95": _percentile(costs, 0.95)},
        "latency_ms": {"p50": median(latencies) if latencies else 0, "p95": _percentile(latencies, 0.95)},
        "cost_by_node": node_costs,
        "latency_by_node_ms": {node: sum(values) / len(states) for node, values in node_latencies.items()} if states else {},
        "cache_hit_rate": cache_hits / total_calls if total_calls else 0.0,
        "cache_calls": total_calls,
        "cache_hits": cache_hits,
        "usd_saved": usd_saved,
        "cold_vs_warm_profile_cost_delta": (sum(profile_cold_costs) / len(profile_cold_costs) if profile_cold_costs else 0) - (sum(profile_warm_costs) / len(profile_warm_costs) if profile_warm_costs else 0),
        "critical_path_waterfall_ms": {node: sum(values) / len(values) for node, values in waterfalls.items() if values},
    }
