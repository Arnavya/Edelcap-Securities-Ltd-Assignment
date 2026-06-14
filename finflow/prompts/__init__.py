"""Versioned prompt templates stored as text files.

The file stem IS the prompt version (e.g. ``investigation_v1``), which is recorded
on every artifact the prompt produces so results are always traceable to a prompt.
"""

from __future__ import annotations

from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parent


def load_prompt(version: str) -> str:
    path = PROMPTS_DIR / f"{version}.txt"
    if not path.exists():
        raise FileNotFoundError(f"unknown prompt version: {version}")
    return path.read_text(encoding="utf-8")
