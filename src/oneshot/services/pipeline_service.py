"""Full pipeline: LLM scene detection + structured analysis of all scenes + film metadata."""

from typing import Any, Awaitable, Callable

from sqlmodel import Session

from oneshot.db_models import Scene
from oneshot.services import scene_service, screenplay_service

ProgressCallback = Callable[[dict], Awaitable[None]]


async def run_full_pipeline(
    screenplay_id: int,
    session: Session,
    provider: str | None = None,
) -> list[Scene]:
    """Detect scenes with LLM, analyze every scene, extract film metadata, and return scenes."""
    return await run_full_pipeline_stream(
        screenplay_id, session, provider=provider, on_progress=None
    )


async def run_full_pipeline_stream(
    screenplay_id: int,
    session: Session,
    provider: str | None = None,
    on_progress: ProgressCallback | None = None,
) -> list[Scene]:
    """Run the full pipeline, optionally reporting progress via on_progress(dict)."""

    async def report(step: str, percent: int, detail: str = ""):
        if on_progress is not None:
            await on_progress(
                {"step": step, "percent": percent, "detail": detail}
            )

    await report("detecting_scenes", 5, "Starting scene detection...")
    scenes = await scene_service.detect_scenes_llm_and_merge(
        screenplay_id, session, provider=provider
    )
    await report("detecting_scenes", 30, f"Found {len(scenes)} scenes.")

    for idx, scene in enumerate(scenes, start=1):
        if not scene.analyzed:
            await report(
                "analyzing_scene",
                30 + int((idx - 0.5) / max(len(scenes), 1) * 50),
                f"Analyzing scene {idx}/{len(scenes)}",
            )
            await scene_service.analyze_scene(scene.id, session, provider=provider)
        elif len(scenes) > 0:
            await report(
                "analyzing_scene",
                30 + int((idx - 0.5) / len(scenes) * 50),
                f"Scene {idx}/{len(scenes)} already analyzed.",
            )

    await report("analyzing_screenplay", 85, "Extracting film metadata...")
    await screenplay_service.analyze_screenplay(screenplay_id, session, provider=provider)
    await report("analyzing_screenplay", 95, "Metadata extracted.")

    result = scene_service.list_scenes(screenplay_id, session)
    await report("complete", 100, "Pipeline complete.")
    return result