"""Scene API routes."""

from fastapi import APIRouter
from oneshot.schemas import Scene, SceneResponse
from oneshot.services import scene_service

router = APIRouter(prefix="/scenes", tags=["scenes"])


@router.post("/analyze", response_model=SceneResponse)
async def analyze_scene(text: str):
    """Analyze screenplay text and return structured scene data."""
    result = await scene_service.analyze(text)
    # TODO: map result to Scene model, persist
    return SceneResponse(
        scenes=[Scene(id="todo", scene_number=1, heading="TODO", location="TODO", **result)],
        screenplay_id="todo",
    )
