"""Scene analysis using an LLM.

Extracts structured scene data and validates it against Pydantic.
"""

import json

from oneshot.ai.json_output import parse_json
from oneshot.ai.llm import generate
from oneshot.ai.prompts import SCENE_ANALYSIS_PROMPT
from oneshot.schemas import SceneAnalysisResult


async def analyze_scene(
    text: str,
    provider: str | None = None,
    model: str | None = None,
) -> SceneAnalysisResult:
    """Analyze raw scene text and return a validated result."""
    prompt = SCENE_ANALYSIS_PROMPT.format(text=text)
    response = await generate(prompt, provider=provider, model=model)

    try:
        data = parse_json(response)
    except json.JSONDecodeError:
        raise ValueError(f"LLM returned invalid JSON: {response}")

    return SceneAnalysisResult.model_validate(data)