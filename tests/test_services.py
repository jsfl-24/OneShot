"""Tests for services."""

from oneshot.services.shot_service import validate_shot


def test_validate_shot_valid():
    """Test that a valid shot passes validation."""
    shot = {
        "shot_type": "Medium",
        "camera_angle": "Eye Level",
        "lens": "50mm",
        "camera_movement": "Static",
        "duration": 5,
        "action": "A man sits.",
    }
    assert validate_shot(shot) is True


def test_validate_shot_missing_field():
    """Test that a shot missing required fields fails validation."""
    shot = {
        "shot_type": "Medium",
        "camera_angle": "Eye Level",
        # missing lens, camera_movement, duration, action
    }
    assert validate_shot(shot) is False
