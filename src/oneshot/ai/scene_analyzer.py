"""Scene analysis using LLM.

Extracts structured scene data from raw screenplay text.
"""

import json
from oneshot.ai.llm import generate
from oneshot.ai.prompts import SCENE_ANALYSIS_PROMPT


async def analyze_scene(text: str) -> dict:
    """Analyze screenplay text and return structured scene data."""
    prompt = SCENE_ANALYSIS_PROMPT.format(text=text)
    response = await generate(prompt)

    try:
        return json.loads(response)
    except json.JSONDecodeError:
        raise ValueError(f"LLM returned invalid JSON: {response}")
