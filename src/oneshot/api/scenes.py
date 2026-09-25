"""Scene API routes."""

import httpx
from fastapi import APIRouter, HTTPException

from oneshot.api.deps import DbSession
from oneshot.api.errors import http_error
from oneshot.schemas import SceneRead, Shot
from oneshot.services import scene_service, shot_service
from oneshot.services.errors import NotFoundError

router = APIRouter(prefix="/scenes", tags=["scenes"])


def _to_read(data: dict) -> SceneRead:
    return SceneRead(**data)


@router.post("/{scene_id}/analyze", response_model=SceneRead)
async def analyze_scene(
    scene_id: int,
    session: DbSession,
    provider: str | None = None,
):
    """Analyze a single scene with the LLM and persist structured data."""
    try:
        scene = await scene_service.analyze_scene(scene_id, session, provider=provider)
    except HTTPException:
        raise
    except (NotFoundError, ValueError, RuntimeError, httpx.RequestError, httpx.HTTPStatusError) as exc:
        raise http_error(exc)
    return _to_read(scene_service.to_dict(scene))


@router.get("/{scene_id}", response_model=SceneRead)
def get_scene(scene_id: int, session: DbSession):
    scene = scene_service.get_scene(scene_id, session)
    if scene is None:
        raise HTTPException(status_code=404, detail=f"Scene {scene_id} not found")
    return _to_read(scene_service.to_dict(scene))


@router.get("/{scene_id}/shots", response_model=list[Shot])
def list_scene_shots(scene_id: int, session: DbSession):
    scene = scene_service.get_scene(scene_id, session)
    if scene is None:
        raise HTTPException(status_code=404, detail=f"Scene {scene_id} not found")
    return [
        shot_service.to_schema(shot, scene.scene_number)
        for shot in shot_service.list_shots(scene_id, session)
    ]