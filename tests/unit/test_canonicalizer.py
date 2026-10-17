from ontology.canonicalizer import Canonicalizer


def test_canonicalizer_resolves_canonical_alias_and_unresolved() -> None:
    canon = Canonicalizer.from_default()
    assert canon.canonicalize("Data Structures & Algorithms").skill_id == canon.canonicalize("DSA").skill_id
    assert canon.canonicalize("CS201 Data Structures").skill_id == canon.canonicalize("Data Structures").skill_id
    result = canon.canonicalize("quantum sandwich engineering")
    assert result.method == "UNRESOLVED"
    assert result.raw_text == "quantum sandwich engineering"


def test_seed_taxonomy_meets_minimum_size() -> None:
    canon = Canonicalizer.from_default()
    assert len(canon.skills) >= 250
    assert sum(len(item.aliases) for item in canon.skills.values()) >= 600
