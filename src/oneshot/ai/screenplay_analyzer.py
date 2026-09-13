"""Screenplay-level analysis using an LLM.

Extracts one-liner, genre, story abstract, and characters from the full screenplay text.
"""

import json

from oneshot.ai.json_output import parse_json
from oneshot.ai.llm import generate
from oneshot.ai.prompts import SCREENPLAY_ANALYSIS_PROMPT
from oneshot.schemas import ScreenplayAnalysisResult


async def analyze_screenplay(
    text: str,
    provider: str | None = None,
    model: str | None = None,
) -> ScreenplayAnalysisResult:
    """Analyze full screenplay text and return validated metadata."""
    prompt = SCREENPLAY_ANALYSIS_PROMPT.format(text=text)
    response = await generate(prompt, provider=provider, model=model)

    try:
        data = parse_json(response)
    except json.JSONDecodeError:
        raise ValueError(f"LLM returned invalid JSON for screenplay analysis: {response}")

    return ScreenplayAnalysisResult.model_validate(data)
