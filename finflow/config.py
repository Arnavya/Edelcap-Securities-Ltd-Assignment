"""Environment-driven configuration.

The whole system is parameterized through a single ``Settings`` object so that
nothing downstream reads ``os.environ`` directly. ``FINFLOW_PROVIDER=mock`` makes
the entire pipeline runnable offline with no API key.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

try:  # python-dotenv is optional at import time (e.g. in minimal CI)
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - fallback when dependency absent
    def load_dotenv(*_args, **_kwargs) -> bool:
        return False


DEFAULT_MODEL = "llama-3.3-70b-versatile"
DEFAULT_DB = "finflow.db"
DEFAULT_RETRIEVAL_K = 4


@dataclass(frozen=True)
class Settings:
    """Resolved runtime configuration."""

    provider: str = "groq"
    groq_api_key: str | None = None
    model: str = DEFAULT_MODEL
    judge_model: str = DEFAULT_MODEL
    db_path: str = DEFAULT_DB
    retrieval_k: int = DEFAULT_RETRIEVAL_K

    @property
    def is_mock(self) -> bool:
        return self.provider == "mock"


def load_settings(*, dotenv: bool = True) -> Settings:
    """Build :class:`Settings` from the environment (and ``.env`` if present)."""

    if dotenv:
        load_dotenv()

    model = os.getenv("FINFLOW_MODEL", DEFAULT_MODEL)
    judge_model = os.getenv("FINFLOW_JUDGE_MODEL") or model

    try:
        retrieval_k = int(os.getenv("FINFLOW_RETRIEVAL_K", str(DEFAULT_RETRIEVAL_K)))
    except ValueError:
        retrieval_k = DEFAULT_RETRIEVAL_K

    return Settings(
        provider=os.getenv("FINFLOW_PROVIDER", "groq").strip().lower(),
        groq_api_key=os.getenv("GROQ_API_KEY") or None,
        model=model,
        judge_model=judge_model,
        db_path=os.getenv("FINFLOW_DB", DEFAULT_DB),
        retrieval_k=retrieval_k,
    )
