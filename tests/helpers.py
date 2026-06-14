"""Test helpers shared across phases."""

from __future__ import annotations

import json

from finflow.llm.base import LLMProvider


class ScriptedProvider(LLMProvider):
    """Returns a fixed response (str or JSON-serializable) for every call.

    Deterministic and offline — lets us drive agents through real code paths with a
    known LLM output, so tests assert on parsing/validation/persistence rather than
    on model behavior.
    """

    def __init__(self, response, *, name: str = "scripted", model: str = "scripted-1") -> None:
        self.name = name
        self.model = model
        self._response = response if isinstance(response, str) else json.dumps(response)
        self.calls: list[str] = []

    def generate(self, prompt, *, system=None, max_tokens=1024, temperature=0.0) -> str:
        self.calls.append(prompt)
        return self._response


class RoutingProvider(LLMProvider):
    """Pick a response by matching a substring in the prompt.

    Lets one provider serve multiple agents (investigation, gap, …) deterministically
    in an end-to-end test. ``rules`` is a list of (substring, response) pairs checked
    in order; ``default`` is used if none match.
    """

    def __init__(self, rules, default="{}", *, name: str = "routing", model: str = "routing-1") -> None:
        self.name = name
        self.model = model
        self._rules = [(s, r if isinstance(r, str) else json.dumps(r)) for s, r in rules]
        self._default = default if isinstance(default, str) else json.dumps(default)
        self.calls: list[str] = []

    def generate(self, prompt, *, system=None, max_tokens=1024, temperature=0.0) -> str:
        self.calls.append(prompt)
        for substring, response in self._rules:
            if substring in prompt:
                return response
        return self._default
