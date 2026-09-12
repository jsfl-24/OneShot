"""Screenplay ingestion and parsing service."""

import shutil
import uuid
from pathlib import Path

from fastapi import UploadFile
from sqlmodel import Session, select

from oneshot.config import settings
from oneshot.db_models import Project, Scene, Screenplay
from oneshot.parsers.document import extract
from oneshot.parsers.scene_detector import detect_scenes


def save_upload(upload: UploadFile) -> Path:
    """Save an uploaded file to the uploads directory and return its path."""
    suffix = Path(upload.filename or "file").suffix
    destination = settings.UPLOAD_DIR / f"{uuid.uuid4().hex}{suffix}"
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("wb") as out:
        shutil.copyfileobj(upload.file, out)
    return destination


def extract_text(file_path: Path, filename: str, project_id: int, session: Session) -> Screenplay:
    """Extract text from a document and persist it as a Screenplay row."""
    text = extract(str(file_path))
    format_ = Path(filename).suffix.lower().lstrip(".") or "txt"

    screenplay = Screenplay(
        project_id=project_id,
        filename=filename,
        format=format_,
        source_path=str(file_path),
        extracted_text=text,
    )
    session.add(screenplay)
    session.commit()
    session.refresh(screenplay)
    return screenplay


def detect_and_persist_scenes(screenplay: Screenplay, session: Session) -> list[Scene]:
    """Detect scenes from screenplay text and persist them."""
    blocks = detect_scenes(screenplay.extracted_text)

    scenes = [
        Scene(
            screenplay_id=screenplay.id,
            project_id=screenplay.project_id,
            scene_number=block.scene_number,
            heading=block.heading,
            location=block.location,
            time_of_day=block.time_of_day,
            raw_text=block.raw_text,
        )
        for block in blocks
    ]
    session.add_all(scenes)
    session.commit()
    for scene in scenes:
        session.refresh(scene)
    return scenes


def ingest_screenplay(
    upload: UploadFile, project_id: int, session: Session
) -> tuple[Screenplay, list[Scene]]:
    """Save, extract, persist, and scene-detect a screenplay file."""
    path = save_upload(upload)
    screenplay = extract_text(path, upload.filename or "untitled", project_id, session)
    scenes = detect_and_persist_scenes(screenplay, session)
    return screenplay, scenes


def get_project(project_id: int, session: Session) -> Project | None:
    return session.get(Project, project_id)


def list_screenplays(project_id: int, session: Session) -> list[Screenplay]:
    statement = select(Screenplay).where(Screenplay.project_id == project_id)
    return list(session.exec(statement).all())


def get_screenplay(screenplay_id: int, session: Session) -> Screenplay | None:
    return session.get(Screenplay, screenplay_id)


def list_scenes(screenplay_id: int, session: Session) -> list[Scene]:
    statement = (
        select(Scene)
        .where(Scene.screenplay_id == screenplay_id)
        .order_by(Scene.scene_number)
    )
    return list(session.exec(statement).all())