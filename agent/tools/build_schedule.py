from agent.contracts import Plan, PlanRequest
from agent.solver import build_schedule as _build_schedule


def build_schedule(request: PlanRequest) -> Plan:
    return _build_schedule(request)
