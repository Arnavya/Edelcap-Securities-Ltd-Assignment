"""Groq provider — the ONLY real LLM provider.

This is the single module permitted to import the Groq SDK. The import is lazy
(inside the client accessor) so the package imports cleanly without the SDK and so
constructing the provider never touches the network.
"""

from __future__ import annotations

from .base import LLMProvider

DEFAULT_MODEL = "llama-3.3-70b-versatile"


class GroqProvider(LLMProvider):
    name = "groq"

    def __init__(self, api_key: str | None, model: str = DEFAULT_MODEL) -> None:
        if not api_key:
            raise ValueError(
                "GROQ_API_KEY is required for the Groq provider. "
                "Set it in your environment/.env, or use FINFLOW_PROVIDER=mock."
            )
        self._api_key = api_key
        self.model = model or DEFAULT_MODEL
        self._client = None  # created lazily on first call

    def _get_client(self):
        if self._client is None:
            try:
                from groq import Groq  # lazy: SDK only needed for real calls
            except ImportError as exc:  # pragma: no cover - environment dependent
                raise RuntimeError(
                    "The 'groq' package is not installed. Run: pip install groq"
                ) from exc
            self._client = Groq(api_key=self._api_key)
        return self._client

    def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.0,
    ) -> str:
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        resp = self._get_client().chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return resp.choices[0].message.content or ""
