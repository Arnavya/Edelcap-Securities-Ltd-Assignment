"""Tolerant JSON extraction from LLM output.

Models (especially via JSON-mode-less providers like Llama) sometimes wrap JSON in
prose or code fences. We extract the outermost JSON object and parse it.
"""

from __future__ import annotations

import json
from typing import Any


def extract_json_object(text: str) -> dict[str, Any]:
    """Return the first top-level JSON object found in ``text``.

    Raises ValueError if none can be parsed.
    """
    if not text:
        raise ValueError("empty LLM response")

    cleaned = text.strip()
    # Strip ```json ... ``` / ``` ... ``` fences if present.
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```", 2)[1] if cleaned.count("```") >= 2 else cleaned
        if cleaned.lstrip().lower().startswith("json"):
            cleaned = cleaned.lstrip()[4:]

    # Fast path.
    try:
        obj = json.loads(cleaned)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass

    # Fallback: scan for a balanced {...} block.
    start = cleaned.find("{")
    if start == -1:
        raise ValueError("no JSON object found in response")
    depth = 0
    in_str = False
    escape = False
    for i in range(start, len(cleaned)):
        ch = cleaned[i]
        if in_str:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                candidate = cleaned[start : i + 1]
                obj = json.loads(candidate)
                if not isinstance(obj, dict):
                    raise ValueError("top-level JSON is not an object")
                return obj
    raise ValueError("unbalanced JSON object in response")
