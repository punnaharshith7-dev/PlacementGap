from __future__ import annotations

from ontology.canonicalizer import Canonicalizer, CanonicalMatch

_CANONICALIZER = Canonicalizer.from_default()


def canonicalize_skill(text: str, context: str | None = None) -> CanonicalMatch:
    return _CANONICALIZER.canonicalize(text, context=context)
