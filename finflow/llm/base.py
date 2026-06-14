"""The LLM provider abstraction.

Intentionally tiny: a single ``generate(prompt) -> str`` method plus an optional
system instruction. This is NOT a chat framework — agents build their own prompts
and (later) parse JSON out of the returned string. Keeping the surface this small
is what makes providers trivially swappable and the mock fully deterministic.

Only files under ``finflow/llm/`` may import a vendor SDK. Everything else depends
on this abstract base.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class LLMProvider(ABC):
    """Abstract text-completion provider.

    Implementations set ``name`` (provider id) and ``model`` (model id).
    """

    name: str = "base"
    model: str = ""

    @abstractmethod
    def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.0,
    ) -> str:
        """Return the model's text completion for ``prompt``.

        ``temperature`` defaults to 0.0 for reproducible behaviour.
        """
        raise NotImplementedError
