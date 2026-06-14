"""Pluggable query-expansion strategies.

Expansion can be supplied two ways, which compose:
- a strategy attached to the retriever (default: none), and
- explicit ``expansion_terms`` passed per ``search`` call (how P6 injects the
  learned ``retrieval_signal`` terms).

Keeping this behind a tiny strategy interface means the learning layer can later
swap in a smarter expander without touching the retriever or the agent.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class ExpansionStrategy(ABC):
    @abstractmethod
    def expand(self, query: str, base_terms: list[str]) -> list[str]:
        """Return extra query terms to widen retrieval."""
        raise NotImplementedError


class NullExpansion(ExpansionStrategy):
    """No expansion (V1 default)."""

    def expand(self, query: str, base_terms: list[str]) -> list[str]:
        return []


class StaticExpansion(ExpansionStrategy):
    """Always contribute a fixed set of terms (useful for tests/demos)."""

    def __init__(self, terms: list[str]) -> None:
        self._terms = list(terms)

    def expand(self, query: str, base_terms: list[str]) -> list[str]:
        return list(self._terms)
