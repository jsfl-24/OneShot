"""Screenplay API routes."""

from fastapi import APIRouter, UploadFile, File
from oneshot.schemas import ScreenplayUpload, ScreenplayResponse
from oneshot.services import screenplay_service

router = APIRouter(prefix="/screenplays", tags=["screenplays"])


@router.post("/upload", response_model=ScreenplayResponse)
async def upload_screenplay(file: UploadFile = File(...)):
    """Upload and extract text from a screenplay file."""
    content = await file.read()
    # TODO: save file, extract text
    return ScreenplayResponse(
        id="todo",
        filename=file.filename,
        format=file.filename.split(".")[-1],
        extracted_text=content.decode(),
        created_at="2025-01-01T00:00:00",
    )
