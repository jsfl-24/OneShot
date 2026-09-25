"""Full pipeline: LLM scene detection + structured analysis of all scenes + film metadata."""

from collections.abc import Awaitable, Callable

from sqlmodel import Session

from oneshot.db_models import Scene
from oneshot.services import scene_service, screenplay_service, shot_service

ProgressCallback = Callable[[dict], Awaitable[None]]


async def run_full_pipeline(
    screenplay_id: int,
    session: Session,
    provider: str | None = None,
    generate_shots: bool = False,
) -> list[Scene]:
    """Detect scenes with LLM, analyze every scene, and extract film metadata.

    When ``generate_shots`` is true, a shot plan is generated for every scene too.
    """
    return await run_full_pipeline_stream(
        screenplay_id,
        session,
        provider=provider,
        generate_shots=generate_shots,
        on_progress=None,
    )


async def run_full_pipeline_stream(
    screenplay_id: int,
    session: Session,
    provider: str | None = None,
    generate_shots: bool = False,
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
    await report("detecting_scenes", 25, f"Found {len(scenes)} scenes.")

    analysis_end = 55 if generate_shots else 80
    analysis_span = analysis_end - 25
    for idx, scene in enumerate(scenes, start=1):
        if not scene.analyzed:
            await report(
                "analyzing_scene",
                25 + int((idx - 0.5) / max(len(scenes), 1) * analysis_span),
                f"Analyzing scene {idx}/{len(scenes)}",
            )
            await scene_service.analyze_scene(scene.id, session, provider=provider)
        elif len(scenes) > 0:
            await report(
                "analyzing_scene",
                25 + int((idx - 0.5) / len(scenes) * analysis_span),
                f"Scene {idx}/{len(scenes)} already analyzed.",
            )

    metadata_end = 60 if generate_shots else 95
    await report("analyzing_screenplay", metadata_end - 10, "Extracting film metadata...")
    await screenplay_service.analyze_screenplay(screenplay_id, session, provider=provider)
    await report("analyzing_screenplay", metadata_end, "Metadata extracted.")

    if generate_shots:
        async def shots_progress(payload: dict):
            await report(
                "generating_shots",
                60 + int(payload.get("percent", 0) * 0.35),
                payload.get("detail", "Generating shots..."),
            )

        await shot_service.generate_shots_for_screenplay(
            session, screenplay_id, provider=provider, on_progress=shots_progress
        )

    result = scene_service.list_scenes(screenplay_id, session)
    await report("complete", 100, "Pipeline complete.")
    return result