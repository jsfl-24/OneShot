from datetime import datetime
from enum import Enum
from typing import List, Optional
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


# --- Screensplay ---

class ScreenplayUpload(BaseModel):
    filename: str
    content: str  # raw extracted text


class ScreenplayResponse(BaseModel):
    id: str
    filename: str
    format: str
    extracted_text: str
    created_at: datetime


# --- Scene ---

class Scene(BaseModel):
    id: str
    scene_number: int
    heading: str
    location: str
    time_of_day: Optional[str] = None
    characters: List[str] = []
    actions: List[str] = []
    dialogue: List[str] = []
    narrative_context: Optional[str] = None


class SceneResponse(BaseModel):
    scenes: List[Scene]
    screenplay_id: str


# --- Production Constraints ---

class ProductionConstraints(BaseModel):
    location_constraints: Optional[str] = None
    camera_movement_allowed: List[CameraMovement] = [CameraMovement.STATIC]
    high_angle_possible: bool = False
    low_angle_possible: bool = False
    available_lenses: List[str] = ["50mm"]
    equipment_constraints: Optional[str] = None
    director_preferences: Optional[str] = None
    additional_notes: Optional[str] = None


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
    characters: List[str] = []
    dialogue: Optional[str] = None
    action: str
    visual_description: str
    continuity_notes: Optional[str] = None
    director_notes: Optional[str] = None
    status: ShotStatus = ShotStatus.DRAFT


class ShotListResponse(BaseModel):
    shots: List[Shot]
    scene_id: str
    scene_heading: str


class ShotUpdate(BaseModel):
    shot_type: Optional[ShotType] = None
    camera_angle: Optional[CameraAngle] = None
    lens: Optional[str] = None
    camera_movement: Optional[CameraMovement] = None
    duration: Optional[int] = None
    characters: Optional[List[str]] = None
    dialogue: Optional[str] = None
    action: Optional[str] = None
    visual_description: Optional[str] = None
    continuity_notes: Optional[str] = None
    director_notes: Optional[str] = None
    status: Optional[ShotStatus] = None


# --- Storyboard ---

class StoryboardPrompt(BaseModel):
    shot_id: str
    prompt: str
    negative_prompt: Optional[str] = None


class StoryboardImage(BaseModel):
    shot_id: str
    prompt: str
    image_path: str
