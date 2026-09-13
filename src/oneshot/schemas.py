from datetime import datetime
from enum import Enum

from pydantic import BaseModel

# --- Enums ---

class ShotType(str, Enum):
    EXTREME_WIDE = "Extreme Wide"
    WIDE = "Wide"
    MEDIUM_WIDE = "Medium Wide"
    MEDIUM = "Medium"
    MEDIUM_CLOSE_UP = "Medium Close-Up"
    CLOSE_UP = "Close-Up"
    EXTREME_CLOSE_UP = "Extreme Close-Up"


class CameraAngle(str, Enum):
    EYE_LEVEL = "Eye Level"
    HIGH_ANGLE = "High Angle"
    LOW_ANGLE = "Low Angle"
    BIRDS_EYE = "Bird's Eye"
    DUTCH_ANGLE = "Dutch Angle"
    WORMS_EYE = "Worm's Eye"


class CameraMovement(str, Enum):
    STATIC = "Static"
    PAN = "Pan"
    TILT = "Tilt"
    DOLLY = "Dolly"
    TRACK = "Track"
    CRANE = "Crane"
    HANDHELD = "Handheld"


class ShotStatus(str, Enum):
    DRAFT = "draft"
    APPROVED = "approved"


# --- Project ---

class ProjectCreate(BaseModel):
    name: str
    description: str | None = None


class ProjectRead(BaseModel):
    id: int
    name: str
    description: str | None = None
    created_at: datetime
    updated_at: datetime


# --- Screenplay ---

class ScreenplayUpload(BaseModel):
    filename: str
    content: str  # raw extracted text


class ScreenplayAnalysisResult(BaseModel):
    one_liner: str
    genre: str
    story_abstract: str
    characters: list[str]


class ScreenplayResponse(BaseModel):
    id: int
    project_id: int
    filename: str
    format: str
    source_path: str
    one_liner: str | None = None
    genre: str | None = None
    story_abstract: str | None = None
    characters: list[str] = []
    analyzed: bool = False
    created_at: datetime


# --- Scene ---

class SceneAnalysisResult(BaseModel):
    characters: list[str]
    actions: list[str]
    dialogue: list[str]
    narrative_context: str


class Scene(BaseModel):
    id: str
    scene_number: int
    heading: str
    location: str
    time_of_day: str | None = None
    characters: list[str] = []
    actions: list[str] = []
    dialogue: list[str] = []
    narrative_context: str | None = None


class SceneRead(BaseModel):
    """Detected scene block from Phase 2 extraction (pre-analysis)."""

    id: int
    screenplay_id: int
    scene_number: int
    heading: str
    location: str
    time_of_day: str | None = None
    raw_text: str
    characters: list[str] = []
    actions: list[str] = []
    dialogue: list[str] = []
    narrative_context: str | None = None
    analyzed: bool = False


class SceneListResponse(BaseModel):
    screenplay_id: int
    total_scenes: int
    scenes: list[SceneRead]


class SceneResponse(BaseModel):
    scenes: list[Scene]
    screenplay_id: str


# --- Production Constraints ---

class ProductionConstraints(BaseModel):
    location_constraints: str | None = None
    camera_movement_allowed: list[CameraMovement] = [CameraMovement.STATIC]
    high_angle_possible: bool = False
    low_angle_possible: bool = False
    available_lenses: list[str] = ["50mm"]
    equipment_constraints: str | None = None
    director_preferences: str | None = None
    additional_notes: str | None = None


# --- Shot ---

class Shot(BaseModel):
    id: str
    scene_id: str
    shot_number: int
    shot_type: ShotType
    camera_angle: CameraAngle
    lens: str
    camera_movement: CameraMovement
    duration: int  # seconds
    characters: list[str] = []
    dialogue: str | None = None
    action: str
    visual_description: str
    continuity_notes: str | None = None
    director_notes: str | None = None
    status: ShotStatus = ShotStatus.DRAFT


class ShotListResponse(BaseModel):
    shots: list[Shot]
    scene_id: str
    scene_heading: str


class ShotUpdate(BaseModel):
    shot_type: ShotType | None = None
    camera_angle: CameraAngle | None = None
    lens: str | None = None
    camera_movement: CameraMovement | None = None
    duration: int | None = None
    characters: list[str] | None = None
    dialogue: str | None = None
    action: str | None = None
    visual_description: str | None = None
    continuity_notes: str | None = None
    director_notes: str | None = None
    status: ShotStatus | None = None


# --- Storyboard ---

class StoryboardPrompt(BaseModel):
    shot_id: str
    prompt: str
    negative_prompt: str | None = None


class StoryboardImage(BaseModel):
    shot_id: str
    prompt: str
    image_path: str
