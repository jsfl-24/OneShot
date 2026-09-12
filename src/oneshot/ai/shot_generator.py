"""Shot generation using LLM.

Generates a shot list from a structured scene + production constraints.
"""

import json
from oneshot.ai.llm import generate
from oneshot.ai.prompts import SHOT_GENERATION_PROMPT


async def generate_shots(scene: dict, constraints: dict | None = None) -> list[dict]:
    """Generate a shot list from a scene and optional constraints."""
    prompt = SHOT_GENERATION_PROMPT.format(
        scene_json=json.dumps(scene, indent=2),
        constraints_json=json.dumps(constraints or {}, indent=2),
    )
    response = await generate(prompt)

    try:
        return json.loads(response)
    except json.JSONDecodeError:
        raise ValueError(f"LLM returned invalid JSON: {response}")
