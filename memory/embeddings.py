from __future__ import annotations

import hashlib
import math
import re


def embed_text(text: str, dimensions: int = 192) -> list[float]:
    """Deterministic offline hashing embedding; swap-in provider can retain this contract."""
    normalized = re.sub(r"\s+", " ", text.casefold()).strip()
    padded = f"  {normalized}  "
    vector = [0.0] * dimensions
    for index in range(max(1, len(padded) - 2)):
        gram = padded[index : index + 3]
        digest = hashlib.blake2b(gram.encode("utf-8"), digest_size=8).digest()
        slot = int.from_bytes(digest[:4], "little") % dimensions
        sign = 1.0 if digest[4] & 1 else -1.0
        vector[slot] += sign
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]


def cosine(left: list[float], right: list[float]) -> float:
    if not left or len(left) != len(right):
        return 0.0
    return sum(a * b for a, b in zip(left, right, strict=True))
