from agent.budget import RunBudget


def test_budget_rejects_calls_that_exceed_cost_or_tokens() -> None:
    budget = RunBudget(max_usd=0.01, max_tokens=100)
    budget.record(node="extract", input_tokens=30, output_tokens=20, cost_usd=0.006)
    assert not budget.can_spend(20, 0.005)
    assert budget.degraded
    assert budget.reduction_reason


def test_budget_tracks_per_node_usage() -> None:
    budget = RunBudget(max_usd=1, max_tokens=1000)
    budget.record(node="critic", input_tokens=10, output_tokens=5, cost_usd=0.02)
    assert budget.node_costs["critic"] == 0.02
