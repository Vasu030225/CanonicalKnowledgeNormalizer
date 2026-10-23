from __future__ import annotations

import hashlib
import math
import re


def deterministic_embedding(text: str, dimensions: int = 64) -> list[float]:
    """Create a stable, normalized feature-hash vector without network access."""
    if dimensions <= 0:
        raise ValueError("Embedding dimensions must be greater than zero.")
    vector = [0.0] * dimensions
    tokens = re.findall(r"\w+", text.lower())
    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % dimensions
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[index] += sign
    norm = math.sqrt(sum(value * value for value in vector))
    if norm:
        vector = [round(value / norm, 8) for value in vector]
    return vector
