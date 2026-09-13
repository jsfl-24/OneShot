"""LLM-based scene detection.

Finds scene boundaries that the regex detector misses: typo'd headings
(e.g. "INT.", "EEXT.") and scenes with no heading at all.
"""

import json

from oneshot.ai.json_output import parse_json
from oneshot.ai.llm import generate
from oneshot.ai.prompts import SCENE_DETECTION_PROMPT


async def detect_scenes(
    text: str,
    provider: str | None = None,
    model: str | None = None,
) -> list[dict]:
    """Return scene detections as a list of dicts with line_number/heading/type."""
    prompt = SCENE_DETECTION_PROMPT.format(text=text)
    response = await generate(prompt, provider=provider, model=model)

    try:
        data = parse_json(response)
    except json.JSONDecodeError:
        raise ValueError(f"LLM returned invalid JSON for scene detection: {response}")

    scenes = data.get("scenes", []) if isinstance(data, dict) else data
    return [s for s in scenes if isinstance(s, dict) and s.get("line_number")]