"""Shared pytest fixtures for OneShot."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine

from oneshot.config import settings
from oneshot.db import get_session
from oneshot.main import app

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture()
def client(tmp_path):
    db_path = tmp_path / "test.db"
    engine = create_engine(
        f"sqlite:///{db_path}", connect_args={"check_same_thread": False}
    )
    SQLModel.metadata.create_all(engine)

    def override_get_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    settings.UPLOAD_DIR = tmp_path / "uploads"

    client = TestClient(app)
    yield client

    app.dependency_overrides.clear()
    engine.dispose()


@pytest.fixture()
def sample_screenplay_path():
    return FIXTURES_DIR / "sample_screenplay.txt"


@pytest.fixture()
def sample_screenplay_pdf_path():
    return FIXTURES_DIR / "sample_screenplay.pdf"


@pytest.fixture()
def sample_screenplay_docx_path():
    return FIXTURES_DIR / "sample_screenplay.docx"