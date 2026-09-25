"""Shot API routes."""

import httpx
from fastapi import APIRouter, HTTPException

from oneshot.api.deps import DbSession
from oneshot.api.errors import http_error
from oneshot.schemas import (
    Shot,
    ShotGenerateRequest,
    ShotListResponse,
)
from oneshot.services import shot_service
from oneshot.services.errors import ConflictError, NotFoundError

router = APIRouter(prefix="/shots", tags=["shots"])


@router.post("/generate", response_model=ShotListResponse)
async def generate_shots(
    payload: ShotGenerateRequest,
    session: DbSession,
    provider: str | None = None,
):
    """Generate and persist a validated shot list for one scene."""
    try:
        return await shot_service.generate_shots_for_scene(
            session,
            payload.scene_id,
            constraints=payload.constraints,
            provider=provider,
            replace_existing=payload.replace_existing,
        )
    except (NotFoundError, ConflictError, ValueError, RuntimeError, httpx.RequestError, httpx.HTTPStatusError) as exc:
        raise http_error(exc)


@router.get("/{shot_id}", response_model=Shot)
def get_shot(shot_id: int, session: DbSession):
    """Retrieve a single shot."""
    shot = shot_service.get_shot_schema(shot_id, session)
    if shot is None:
        raise HTTPException(status_code=404, detail=f"Shot {shot_id} not found")
    return shot