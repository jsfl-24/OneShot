"""Screenplay API routes."""

from typing import Annotated

import httpx
from fastapi import APIRouter, File, HTTPException, UploadFile

from oneshot.api.deps import DbSession
from oneshot.api.errors import http_error
from oneshot.schemas import (
    SceneListResponse,
    SceneRead,
    ScreenplayResponse,
)
from oneshot.services import pipeline_service, scene_service, screenplay_service
from oneshot.services.errors import NotFoundError

router = APIRouter(prefix="/screenplays", tags=["screenplays"])


@router.post("/projects/{project_id}/upload", response_model=ScreenplayResponse)
async def upload_screenplay(
    project_id: int,
    file: Annotated[UploadFile, File()],
    session: DbSession,
):
    if screenplay_service.get_project(project_id, session) is None:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    extension = (file.filename or "").split(".")[-1].lower()
    if extension not in {"pdf", "docx", "txt"}:
        raise HTTPException(
            status_code=415, detail=f"Unsupported file format: .{extension}"
        )

    screenplay, _scenes = screenplay_service.ingest_screenplay(file, project_id, session)
    return ScreenplayResponse(
        id=screenplay.id,
        project_id=screenplay.project_id,
        filename=screenplay.filename,
        format=screenplay.format,
        source_path=screenplay.source_path,
        created_at=screenplay.created_at,
    )


@router.get("/projects/{project_id}", response_model=list[ScreenplayResponse])
def list_screenplays(project_id: int, session: DbSession):
    if screenplay_service.get_project(project_id, session) is None:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    return [
        ScreenplayResponse(
            id=s.id,
            project_id=s.project_id,
            filename=s.filename,
            format=s.format,
            source_path=s.source_path,
            created_at=s.created_at,
        )
        for s in screenplay_service.list_screenplays(project_id, session)
    ]


@router.get("/{screenplay_id}", response_model=ScreenplayResponse)
def get_screenplay(screenplay_id: int, session: DbSession):
    screenplay = screenplay_service.get_screenplay(screenplay_id, session)
    if screenplay is None:
        raise HTTPException(status_code=404, detail=f"Screenplay {screenplay_id} not found")
    return ScreenplayResponse(
        id=screenplay.id,
        project_id=screenplay.project_id,
        filename=screenplay.filename,
        format=screenplay.format,
        source_path=screenplay.source_path,
        created_at=screenplay.created_at,
    )


@router.get("/{screenplay_id}/scenes", response_model=SceneListResponse)
def list_scenes(screenplay_id: int, session: DbSession):
    screenplay = screenplay_service.get_screenplay(screenplay_id, session)
    if screenplay is None:
        raise HTTPException(status_code=404, detail=f"Screenplay {screenplay_id} not found")
    scenes = screenplay_service.list_scenes(screenplay_id, session)
    return SceneListResponse(
        screenplay_id=screenplay_id,
        scenes=[SceneRead(**scene_service.to_dict(s)) for s in scenes],
    )


@router.post("/{screenplay_id}/detect-scenes", response_model=SceneListResponse)
async def detect_scenes(screenplay_id: int, session: DbSession, provider: str | None = None):
    """Run LLM scene detection and merge with regex-detected scenes."""
    try:
        scenes = await scene_service.detect_scenes_llm_and_merge(
            screenplay_id, session, provider=provider
        )
    except HTTPException:
        raise
    except (NotFoundError, ValueError, RuntimeError, httpx.RequestError, httpx.HTTPStatusError) as exc:
        raise http_error(exc)
    return SceneListResponse(
        screenplay_id=screenplay_id,
        scenes=[SceneRead(**scene_service.to_dict(s)) for s in scenes],
    )


@router.post("/{screenplay_id}/full-pipeline", response_model=SceneListResponse)
async def full_pipeline(screenplay_id: int, session: DbSession, provider: str | None = None):
    """LLM-detect scenes then analyze all of them in one stretch."""
    try:
        scenes = await pipeline_service.run_full_pipeline(
            screenplay_id, session, provider=provider
        )
    except HTTPException:
        raise
    except (NotFoundError, ValueError, RuntimeError, httpx.RequestError, httpx.HTTPStatusError) as exc:
        raise http_error(exc)
    return SceneListResponse(
        screenplay_id=screenplay_id,
        scenes=[SceneRead(**scene_service.to_dict(s)) for s in scenes],
    )