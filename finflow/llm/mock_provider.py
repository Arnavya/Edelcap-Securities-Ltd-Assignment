"""Fully deterministic, offline mock provider for tests and CI.

Guarantees:
- same (prompt, system) -> same response, always
- no randomness, no clock, no network
- usable with no API key

Tests (and later phases) can inject canned responses keyed by the exact prompt
string or by the deterministic fingerprint. When no canned response matches, a
stable hash-derived string is returned so behaviour is still deterministic.
"""

from __future__ import annotations

import hashlib

from .base import LLMProvider


def fingerprint(prompt: str, system: str | None = None) -> str:
    """Stable hash of a request — same input always yields the same id."""
    payload = f"{system or ''}\n---\n{prompt}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


class MockProvider(LLMProvider):
    name = "mock"

    def __init__(
        self,
        model: str = "mock-model",
        responses: dict[str, str] | None = None,
    ) -> None:
        """``responses`` may be keyed by the exact prompt OR by its fingerprint."""
        self.model = model
        self._responses = dict(responses or {})

    def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.0,
    ) -> str:
        fp = fingerprint(prompt, system)
        if prompt in self._responses:
            return self._responses[prompt]
        if fp in self._responses:
            return self._responses[fp]
        # Deterministic fallback — never random.
        return f"MOCK[{fp[:12]}]"
