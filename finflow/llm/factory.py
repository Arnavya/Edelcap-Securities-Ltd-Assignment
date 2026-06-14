"""Provider factory — the one place that maps config to a concrete provider.

Adding a future provider (Anthropic/OpenAI/Ollama) means one new module under
``finflow/llm/`` and one new branch here. No business-logic change.
"""

from __future__ import annotations

from ..config import Settings
from .base import LLMProvider
from .groq_provider import GroqProvider
from .mock_provider import MockProvider


def build_provider(settings: Settings) -> LLMProvider:
    provider = settings.provider
    if provider == "mock":
        return MockProvider(model=settings.model)
    if provider == "groq":
        return GroqProvider(api_key=settings.groq_api_key, model=settings.model)
    raise ValueError(
        f"Unknown FINFLOW_PROVIDER '{provider}'. "
        "Implemented providers: 'groq', 'mock'."
    )
