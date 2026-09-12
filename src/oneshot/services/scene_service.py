"""Scene analysis service."""

from oneshot.ai.scene_analyzer import analyze_scene


async def analyze(text: str) -> dict:
    """Analyze screenplay text and return structured scene data."""
    return await analyze_scene(text)
