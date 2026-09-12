"""Shot API routes."""

from fastapi import APIRouter
from oneshot.schemas import Shot, ShotListResponse, ShotUpdate, ProductionConstraints
from oneshot.services import shot_service

router = APIRouter(prefix="/shots", tags=["shots"])


@router.post("/generate", response_model=ShotListResponse)
async def generate_shots(scene: dict, constraints: ProductionConstraints | None = None):
    """Generate a shot list from a scene."""
    shots = await shot_service.generate(scene, constraints.model_dump() if constraints else None)
    # TODO: map to Shot model, persist
    return ShotListResponse(
        shots=[Shot(id=f"todo_{i}", scene_id="todo", shot_number=i+1, **s) for i, s in enumerate(shots)],
        scene_id="todo",
        scene_heading="TODO",
    )


@router.patch("/{shot_id}", response_model=Shot)
async def update_shot(shot_id: str, update: ShotUpdate):
    """Update a shot's fields."""
    # TODO: retrieve, apply update, persist
    pass
