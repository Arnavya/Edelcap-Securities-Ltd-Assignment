"""Deterministic improvement math (V1 -> V2)."""

from __future__ import annotations

_EPS = 1e-6

# Success signal: rubric-coverage + similarity (NOT source retrieval).
BLEND_SIMILARITY = 0.5
BLEND_ROOT_CAUSE = 0.5


def blended(similarity: float, root_cause: float) -> float:
    return round(BLEND_SIMILARITY * similarity + BLEND_ROOT_CAUSE * root_cause, 4)


def relative_improvement(v1: float, v2: float) -> float:
    return round((v2 - v1) / max(v1, _EPS), 4)
