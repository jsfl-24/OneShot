"""Database models (ORM tables).

Kept separate from API schemas in `schemas.py`.
"""

from datetime import UTC, datetime

from sqlalchemy import JSON, Column
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
    one_liner: str | None = None
    genre: str | None = None
    story_abstract: str | None = None
    characters: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    analyzed: bool = Field(default=False)
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
    characters: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    actions: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    dialogue: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    narrative_context: str | None = None
    analyzed: bool = Field(default=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Shot(SQLModel, table=True):
    __tablename__ = "shots"

    id: int | None = Field(default=None, primary_key=True)
    scene_id: int = Field(foreign_key="scenes.id", index=True)
    shot_number: int
    shot_type: str
    camera_angle: str
    lens: str
    camera_movement: str
    duration: int
    characters: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    dialogue: str | None = None
    action: str
    visual_description: str
    continuity_notes: str | None = None
    director_notes: str | None = None
    status: str = Field(default="draft")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ProductionConstraints(SQLModel, table=True):
    __tablename__ = "production_constraints"

    # Only explicitly provided fields are stored; NULL fields inherit from the
    # level below during the project -> scene merge.
    id: int | None = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="projects.id", index=True)
    scene_id: int | None = Field(default=None, foreign_key="scenes.id", index=True)
    location_constraints: str | None = None
    camera_movement_allowed: list[str] | None = Field(default=None, sa_column=Column(JSON))
    high_angle_possible: bool | None = None
    low_angle_possible: bool | None = None
    available_lenses: list[str] | None = Field(default=None, sa_column=Column(JSON))
    equipment_constraints: str | None = None
    director_preferences: str | None = None
    additional_notes: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))