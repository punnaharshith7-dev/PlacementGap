from __future__ import annotations

from agent.nodes.jd_extract import _rule_extract
from ontology.canonicalizer import Canonicalizer


def test_requirement_extraction_ignores_role_header_and_matches_punctuation_aliases() -> None:
    job_text = (
        "Machine Learning Engineer: Python is required. Machine Learning is required. "
        "A/B Testing is preferred."
    )
    requirements = _rule_extract(job_text, "jd:test", Canonicalizer.from_default(), "Machine Learning Engineer")
    by_id = {item.skill_id: item for item in requirements}

    assert set(by_id) == {"python", "machine-learning", "a-b-testing"}
    assert by_id["machine-learning"].span.char_start == job_text.index("Machine Learning is")
    assert by_id["a-b-testing"].hard_requirement is False
    assert by_id["python"].hard_requirement is True
