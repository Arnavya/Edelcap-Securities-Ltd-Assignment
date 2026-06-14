"""Deterministic anti-leakage gate.

Learning events must never contain verbatim expert-answer text. This module detects
shared word n-grams between a candidate text and the expert answer and, aggressively,
DROPS any learning pattern whose free-text fields share an n-gram with the reference.
No LLM, fully reproducible — the authoritative enforcement of the no-verbatim rule.
"""

from __future__ import annotations

import re

from ..models import LearningPattern

NGRAM_N = 5  # aggressive: a 5-word overlap with the expert answer is treated as leakage
_WORD_RE = re.compile(r"[a-z0-9]+")

# Free-text fields of a LearningPattern that must be answer-free.
_TEXT_FIELDS = ("hint_text", "trigger_conditions")


def _words(text: str) -> list[str]:
    return _WORD_RE.findall((text or "").lower())


def _ngrams(tokens: list[str], n: int) -> list[tuple[str, ...]]:
    return [tuple(tokens[i : i + n]) for i in range(len(tokens) - n + 1)] if len(tokens) >= n else []


def overlap_fraction(text: str, reference: str, n: int = NGRAM_N) -> float:
    """Fraction of ``text``'s n-grams that also appear in ``reference``."""
    tg = _ngrams(_words(text), n)
    if not tg:
        return 0.0
    ref = set(_ngrams(_words(reference), n))
    return sum(1 for g in tg if g in ref) / len(tg)


def contains_verbatim(text: str, reference: str, n: int = NGRAM_N) -> bool:
    """True if ``text`` shares any n-gram with ``reference``."""
    if not text:
        return False
    ref = set(_ngrams(_words(reference), n))
    return any(g in ref for g in _ngrams(_words(text), n))


def pattern_text_fields(pattern: LearningPattern) -> list[str]:
    return [getattr(pattern, f, "") or "" for f in _TEXT_FIELDS]


def pattern_leaks(pattern: LearningPattern, reference: str, n: int = NGRAM_N) -> bool:
    return any(contains_verbatim(t, reference, n) for t in pattern_text_fields(pattern))


def sanitize_patterns(
    patterns: list[LearningPattern], reference: str, n: int = NGRAM_N
) -> tuple[list[LearningPattern], int, float]:
    """Drop any pattern that shares an n-gram with the reference (expert answer).

    Returns (kept_patterns, dropped_count, max_overlap_fraction_observed).
    """
    kept: list[LearningPattern] = []
    dropped = 0
    max_overlap = 0.0
    for p in patterns:
        leak = False
        for t in pattern_text_fields(p):
            max_overlap = max(max_overlap, overlap_fraction(t, reference, n))
            if contains_verbatim(t, reference, n):
                leak = True
        if leak:
            dropped += 1
        else:
            kept.append(p)
    return kept, dropped, round(max_overlap, 4)
