"""Shared test fixtures.

Tests must run fully offline. As later phases land, the mock provider and an
in-memory repository fixture will live here.
"""

import os

import pytest


@pytest.fixture(autouse=True)
def _offline_env(monkeypatch):
    """Force the mock provider so no test can accidentally hit a network API."""
    monkeypatch.setenv("FINFLOW_PROVIDER", "mock")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    yield
