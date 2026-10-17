from __future__ import annotations

from agent.contracts import SkillLevel

_BASE_HOURS = {
    ("aware", "can_use"): 3.0,
    ("aware", "can_build"): 12.0,
    ("aware", "can_design"): 28.0,
    ("can_use", "can_build"): 9.0,
    ("can_use", "can_design"): 22.0,
    ("can_build", "can_design"): 14.0,
}


def estimate_effort(skill_id: str, from_level: SkillLevel, to_level: SkillLevel) -> float:
    """Calibrated effort lookup; never delegates arithmetic to a model."""
    del skill_id  # Skill-specific multipliers can be loaded from the calibration table.
    if from_level.rank >= to_level.rank:
        return 1.0
    return _BASE_HOURS.get((from_level.value, to_level.value), 8.0)
