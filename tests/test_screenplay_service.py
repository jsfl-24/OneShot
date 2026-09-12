"""Tests for the screenplay ingestion service."""

import io

from fastapi import UploadFile
from sqlmodel import Session, SQLModel, create_engine, select

from oneshot.db_models import Scene, Screenplay
from oneshot.services import screenplay_service


def test_extract_and_persist_screenplay(sample_screenplay_path):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}
    )
    SQLModel.metadata.create_all(engine)

    upload = UploadFile(
        filename=sample_screenplay_path.name,
        file=io.BytesIO(sample_screenplay_path.read_bytes()),
    )

    with Session(engine) as session:
        screenplay = screenplay_service.extract_text(
            sample_screenplay_path, upload.filename, project_id=1, session=session
        )

        assert screenplay.id is not None
        assert screenplay.project_id == 1
        assert screenplay.filename == sample_screenplay_path.name
        assert screenplay.format == "txt"
        assert "COFFEE SHOP" in screenplay.extracted_text


def test_detect_and_persist_scenes(sample_screenplay_path):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        screenplay = Screenplay(
            project_id=1,
            filename="sample_screenplay.txt",
            format="txt",
            source_path=str(sample_screenplay_path),
            extracted_text=sample_screenplay_path.read_text(encoding="utf-8"),
        )
        session.add(screenplay)
        session.commit()
        session.refresh(screenplay)

        scenes = screenplay_service.detect_and_persist_scenes(screenplay, session)

        assert len(scenes) == 4
        assert scenes[0].scene_number == 1
        assert scenes[0].location == "COFFEE SHOP"
        assert scenes[0].screenplay_id == screenplay.id

        stored = session.exec(select(Scene)).all()
        assert len(stored) == 4


def test_get_screenplay_and_scenes(sample_screenplay_path):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        screenplay = Screenplay(
            project_id=1,
            filename="sample_screenplay.txt",
            format="txt",
            source_path=str(sample_screenplay_path),
            extracted_text=sample_screenplay_path.read_text(encoding="utf-8"),
        )
        session.add(screenplay)
        session.commit()
        session.refresh(screenplay)

        screenplay_service.detect_and_persist_scenes(screenplay, session)

        found = screenplay_service.get_screenplay(screenplay.id, session)
        assert found is not None
        assert found.filename == "sample_screenplay.txt"

        scenes = screenplay_service.list_scenes(screenplay.id, session)
        assert len(scenes) == 4