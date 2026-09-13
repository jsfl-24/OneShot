"""Helpers for parsing strict JSON out of LLM responses."""

import json
from typing import Any


def parse_json(text: str) -> Any:
    """Parse JSON, tolerating markdown code fences around the payload."""
    raw = text.strip()
    if raw.startswith("```"):
        lines = raw.splitlines()
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        raw = "\n".join(lines).strip()
    return json.loads(raw)