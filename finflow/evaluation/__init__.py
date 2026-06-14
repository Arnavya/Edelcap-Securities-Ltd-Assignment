"""Evaluation helpers.

This package __init__ stays dependency-light (only pure helpers) to avoid an import
cycle: ``agents`` imports the leakage gate from here, while ``Judge``/``Evaluator``
import ``agents``/``orchestrator``. Import those two from their submodules:
``finflow.evaluation.judge`` and ``finflow.evaluation.evaluator``.
"""

from .evidence_overlap import compute_overlap
from .improvement import blended, relative_improvement
from .leakage import (
    NGRAM_N,
    contains_verbatim,
    overlap_fraction,
    pattern_leaks,
    sanitize_patterns,
)

__all__ = [
    "compute_overlap",
    "blended",
    "relative_improvement",
    "NGRAM_N",
    "contains_verbatim",
    "overlap_fraction",
    "pattern_leaks",
    "sanitize_patterns",
]
