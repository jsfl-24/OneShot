"""Production constraints API routes.

Project-level defaults and per-scene overrides. ``GET .../scenes/{scene_id}/constraints``
returns the merged (effective) constraints for that scene.
"""

from fastapi import APIRouter, HTTPException

from oneshot.api.deps import DbSession
from oneshot.schemas import ProductionConstraints
from oneshot.services import scene_service, screenplay_service, shot_service

router = APIRouter(prefix="/projects", tags=["constraints"])


@router.put("/{project_id}/constraints", response_model=ProductionConstraints)
def set_project_constraints(project_id: int, data: ProductionConstraints, session: DbSession):
    if screenplay_service.get_project(project_id, session) is None:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    shot_service.set_constraints(session, project_id, None, data)
    merged = shot_service.effective_constraints(session, project_id)
    return ProductionConstraints(**merged)


@router.get("/{project_id}/constraints", response_model=ProductionConstraints)
def get_project_constraints(project_id: int, session: DbSession):
    if screenplay_service.get_project(project_id, session) is None:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    merged = shot_service.effective_constraints(session, project_id)
    return ProductionConstraints(**merged)


@router.put(
    "/{project_id}/scenes/{scene_id}/constraints",
    response_model=ProductionConstraints,
)
def set_scene_constraints(
    project_id: int, scene_id: int, data: ProductionConstraints, session: DbSession
):
    if scene_service.get_scene(scene_id, session) is None:
        raise HTTPException(status_code=404, detail=f"Scene {scene_id} not found")
    shot_service.set_constraints(session, project_id, scene_id, data)
    merged = shot_service.effective_constraints(session, project_id, scene_id)
    return ProductionConstraints(**merged)


@router.get(
    "/{project_id}/scenes/{scene_id}/constraints",
    response_model=ProductionConstraints,
)
def get_scene_constraints(project_id: int, scene_id: int, session: DbSession):
    """Return the effective (merged) constraints for a scene."""
    if scene_service.get_scene(scene_id, session) is None:
        raise HTTPException(status_code=404, detail=f"Scene {scene_id} not found")
    merged = shot_service.effective_constraints(session, project_id, scene_id)
    return ProductionConstraints(**merged)