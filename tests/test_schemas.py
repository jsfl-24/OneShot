"""Tests for Pydantic schemas."""

from oneshot.schemas import CameraAngle, CameraMovement, Shot, ShotStatus, ShotType


def test_shot_creation():
    """Test that a Shot can be created with valid data."""
    shot = Shot(
        id="S01_SH01",
        scene_id="S01",
        shot_number=1,
        shot_type=ShotType.MEDIUM,
        camera_angle=CameraAngle.EYE_LEVEL,
        lens="50mm",
        camera_movement=CameraMovement.STATIC,
        duration=5,
        action="A man sits at a desk.",
        visual_description="Medium shot of a man at his desk.",
    )
    assert shot.shot_type == ShotType.MEDIUM
    assert shot.status == ShotStatus.DRAFT
    assert shot.duration == 5


def test_shot_defaults():
    """Test that Shot defaults are applied correctly."""
    shot = Shot(
        id="S01_SH01",
        scene_id="S01",
        shot_number=1,
        shot_type=ShotType.CLOSE_UP,
        camera_angle=CameraAngle.HIGH_ANGLE,
        lens="85mm",
        camera_movement=CameraMovement.PAN,
        duration=3,
        action="She looks up.",
        visual_description="Close-up of her face.",
    )
    assert shot.status == ShotStatus.DRAFT
    assert shot.characters == []
    assert shot.dialogue is None
