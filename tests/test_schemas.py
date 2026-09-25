"""Tests for Pydantic schemas."""

import pytest

from oneshot.schemas import (
    AIShotData,
    CameraAngle,
    CameraMovement,
    Shot,
    ShotStatus,
    ShotType,
    shot_ref,
)


def test_shot_ref():
    assert shot_ref(1, 3) == "Scene 01 - Shot 03"


def test_shot_creation():
    """Test that a Shot can be created with valid data."""
    shot = Shot(
        id=1,
        scene_id=1,
        scene_number=1,
        shot_number=1,
        shot_type=ShotType.MEDIUM,
        camera_angle=CameraAngle.EYE_LEVEL,
        lens="50mm",
        camera_movement=CameraMovement.STATIC,
        duration=5,
        action="A man sits at a desk.",
        visual_description="Medium shot of a man at his desk.",
        ref=shot_ref(1, 1),
    )
    assert shot.shot_type == ShotType.MEDIUM
    assert shot.status == ShotStatus.DRAFT
    assert shot.duration == 5
    assert shot.ref == "Scene 01 - Shot 01"


def test_shot_defaults():
    """Test that Shot defaults are applied correctly."""
    shot = Shot(
        id=1,
        scene_id=1,
        scene_number=1,
        shot_number=1,
        shot_type=ShotType.CLOSE_UP,
        camera_angle=CameraAngle.HIGH_ANGLE,
        lens="85mm",
        camera_movement=CameraMovement.PAN,
        duration=3,
        action="She looks up.",
        visual_description="Close-up of her face.",
        ref=shot_ref(1, 1),
    )
    assert shot.status == ShotStatus.DRAFT
    assert shot.characters == []
    assert shot.dialogue is None


def _ai_payload(**overrides):
    payload = {
        "shot_type": "Medium",
        "camera_angle": "Eye Level",
        "lens": "50mm",
        "camera_movement": "Static",
        "duration": 5,
        "action": "A man sits.",
        "visual_description": "A man sits at a desk.",
    }
    payload.update(overrides)
    return payload


def test_ai_shot_data_validates_enum_values():
    shot = AIShotData.model_validate(_ai_payload())
    assert shot.shot_type is ShotType.MEDIUM
    assert shot.camera_angle is CameraAngle.EYE_LEVEL
    assert shot.camera_movement is CameraMovement.STATIC


def test_ai_shot_data_rejects_non_enum_value():
    with pytest.raises(ValueError):
        AIShotData.model_validate(_ai_payload(shot_type="MCU"))


def test_ai_shot_data_rejects_out_of_range_duration():
    with pytest.raises(ValueError):
        AIShotData.model_validate(_ai_payload(duration=0))
    with pytest.raises(ValueError):
        AIShotData.model_validate(_ai_payload(duration=999))