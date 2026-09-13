"""Database models (ORM tables).

Kept separate from API schemas in `schemas.py`.
"""

from datetime import UTC, datetime

from sqlmodel import Field, SQLModel


class Project(SQLModel, table=True):
    __tablename__ = "projects"

    id: int | None = Field(default=None, primary_key=True)
    name: str
    description: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Screenplay(SQLModel, table=True):
    __tablename__ = "screenplays"

    id: int | None = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="projects.id", index=True)
    filename: str
    format: str
    source_path: str
    extracted_text: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Scene(SQLModel, table=True):
    __tablename__ = "scenes"

    id: int | None = Field(default=None, primary_key=True)
    screenplay_id: int = Field(foreign_key="screenplays.id", index=True)
    project_id: int = Field(foreign_key="projects.id", index=True)
    scene_number: int
    heading: str
    location: str
    time_of_day: str | None = None
    raw_text: str
    characters: str = Field(default="[]")
    actions: str = Field(default="[]")
    dialogue: str = Field(default="[]")
    narrative_context: str | None = None
    analyzed: bool = Field(default=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))