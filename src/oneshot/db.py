"""Database engine, session, and initialization."""

from collections.abc import Generator
from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine

from oneshot.config import settings

engine = create_engine(settings.DATABASE_URL, connect_args={"check_same_thread": False})


def init_db() -> None:
    if settings.DATABASE_URL.startswith("sqlite"):
        db_path = settings.DATABASE_URL.replace("sqlite:///", "")
        base_dir = Path(db_path).parent
        if db_path and str(base_dir) not in ("", "."):
            base_dir.mkdir(parents=True, exist_ok=True)
    SQLModel.metadata.create_all(engine)


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session