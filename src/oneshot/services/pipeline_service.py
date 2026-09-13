"""Full pipeline: LLM scene detection + structured analysis of all scenes."""

from sqlmodel import Session

from oneshot.db_models import Scene
from oneshot.services import scene_service


async def run_full_pipeline(
    screenplay_id: int,
    session: Session,
    provider: str | None = None,
) -> list[Scene]:
    """Detect scenes with LLM, then analyze every scene, and return them."""
    scenes = await scene_service.detect_scenes_llm_and_merge(
        screenplay_id, session, provider=provider
    )

    for scene in scenes:
        if not scene.analyzed:
            await scene_service.analyze_scene(scene.id, session, provider=provider)

    return scene_service.list_scenes(screenplay_id, session)