"""P1: LLM provider abstraction tests — all run offline."""

import socket
from pathlib import Path

import pytest

from finflow.config import load_settings
from finflow.llm import GroqProvider, MockProvider, build_provider
from finflow.llm.base import LLMProvider
from finflow.llm.mock_provider import fingerprint


# --- MockProvider: deterministic, no key, no network -------------------------

def test_mock_provider_works_without_api_key(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    p = MockProvider()
    out = p.generate("Why did the release slip?")
    assert isinstance(out, str) and out


def test_mock_provider_is_deterministic():
    p = MockProvider()
    a = p.generate("same prompt", system="sys")
    b = p.generate("same prompt", system="sys")
    assert a == b  # same input -> same output, always
    # different input -> (almost surely) different output
    assert p.generate("other prompt") != a


def test_mock_provider_canned_responses():
    p = MockProvider(responses={"ping": "pong"})
    assert p.generate("ping") == "pong"
    # also addressable by fingerprint
    fp = fingerprint("hello", "sys")
    p2 = MockProvider(responses={fp: "canned"})
    assert p2.generate("hello", system="sys") == "canned"


def test_mock_makes_no_network_call(monkeypatch):
    """Hard-disable sockets, then prove the mock still answers."""

    def _boom(*_a, **_k):
        raise AssertionError("network access attempted under mock provider")

    monkeypatch.setattr(socket, "socket", _boom)
    monkeypatch.setattr(socket, "create_connection", _boom)
    monkeypatch.setattr(socket, "getaddrinfo", _boom)

    settings = load_settings(dotenv=False)  # FINFLOW_PROVIDER=mock via conftest
    provider = build_provider(settings)
    assert provider.generate("anything")  # would raise if it touched the network


# --- Factory: returns the correct provider -----------------------------------

def test_factory_returns_mock(monkeypatch):
    monkeypatch.setenv("FINFLOW_PROVIDER", "mock")
    provider = build_provider(load_settings(dotenv=False))
    assert isinstance(provider, MockProvider)
    assert provider.name == "mock"


def test_factory_returns_groq(monkeypatch):
    monkeypatch.setenv("FINFLOW_PROVIDER", "groq")
    monkeypatch.setenv("GROQ_API_KEY", "dummy-key-for-construction")
    provider = build_provider(load_settings(dotenv=False))
    assert isinstance(provider, GroqProvider)
    assert provider.name == "groq"
    assert provider.model  # default model applied


def test_factory_unknown_provider(monkeypatch):
    monkeypatch.setenv("FINFLOW_PROVIDER", "wat")
    with pytest.raises(ValueError, match="Unknown FINFLOW_PROVIDER"):
        build_provider(load_settings(dotenv=False))


# --- GroqProvider: fails gracefully without a key ----------------------------

def test_groq_requires_api_key():
    with pytest.raises(ValueError, match="GROQ_API_KEY is required"):
        GroqProvider(api_key=None)


def test_factory_groq_without_key_fails_gracefully(monkeypatch):
    monkeypatch.setenv("FINFLOW_PROVIDER", "groq")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    with pytest.raises(ValueError, match="GROQ_API_KEY is required"):
        build_provider(load_settings(dotenv=False))


def test_provider_subclasses_base():
    assert issubclass(MockProvider, LLMProvider)
    assert issubclass(GroqProvider, LLMProvider)


# --- Isolation: only groq_provider.py may import the Groq SDK ----------------

def test_groq_sdk_is_isolated():
    finflow_root = Path(__file__).resolve().parent.parent / "finflow"
    offenders = []
    for path in finflow_root.rglob("*.py"):
        if path.name == "groq_provider.py":
            continue
        text = path.read_text(encoding="utf-8")
        if "import groq" in text or "from groq" in text:
            offenders.append(str(path.relative_to(finflow_root)))
    assert not offenders, f"Groq SDK imported outside groq_provider.py: {offenders}"
