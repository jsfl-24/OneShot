"""Tests for service-layer logic: shot validation, continuity, and constraint merging."""

from sqlmodel import Session, SQLModel, create_engine

from oneshot.db_models import Shot
from oneshot.schemas import (
    AIShotData,
    CameraAngle,
    CameraMovement,
    ProductionConstraints,
    ShotType,
)
from oneshot.services import shot_service


def _scene(**overrides):
    from oneshot.db_models import Scene

    base = {
        "screenplay_id": 1,
        "project_id": 1,
        "scene_number": 1,
        "heading": "INT. ROOM - DAY",
        "location": "ROOM",
        "raw_text": "",
        "characters": ["JANE"],
    }
    base.update(overrides)
    return Scene(**base)


def _ai(**overrides):
    payload = {
        "shot_type": ShotType.MEDIUM,
        "camera_angle": CameraAngle.EYE_LEVEL,
        "lens": "50mm",
        "camera_movement": CameraMovement.STATIC,
        "duration": 5,
        "characters": ["JANE"],
        "action": "JANE looks up.",
        "visual_description": "Medium shot of JANE sitting.",
    }
    payload.update(overrides)
    return AIShotData(**payload)


def _constraints(**overrides):
    base = {
        "camera_movement_allowed": ["Static", "Dolly"],
        "high_angle_possible": True,
        "low_angle_possible": True,
        "available_lenses": ["50mm", "85mm"],
    }
    base.update(overrides)
    return base


def test_validate_shot_valid():
    errors, warnings = shot_service.validate_shot(
        _ai(), _scene(), _constraints()
    )
    assert errors == []
    assert warnings == []


def test_validate_shot_unknown_character_warns():
    errors, warnings = shot_service.validate_shot(
        _ai(characters=["BOB"]), _scene(), _constraints()
    )
    assert errors == []
    assert any("BOB" in message for message in warnings)


def test_validate_shot_lens_not_available_is_error():
    errors, _ = shot_service.validate_shot(
        _ai(lens="35mm"), _scene(), _constraints(available_lenses=["50mm"])
    )
    assert any("not in available lenses" in error for error in errors)


def test_validate_shot_movement_not_allowed_is_error():
    errors, _ = shot_service.validate_shot(
        _ai(camera_movement=CameraMovement.CRANE),
        _scene(),
        _constraints(camera_movement_allowed=["Static"]),
    )
    assert any("camera movement" in error for error in errors)


def test_validate_shot_angle_overridden_creates_no_error():
    errors, _ = shot_service.validate_shot(
        _ai(camera_angle=CameraAngle.HIGH_ANGLE), _scene(), _constraints()
    )
    assert errors == []


def test_validate_shot_disallowed_angle_is_error():
    errors, _ = shot_service.validate_shot(
        _ai(camera_angle=CameraAngle.LOW_ANGLE),
        _scene(),
        _constraints(low_angle_possible=False),
    )
    assert any("low angle" in error for error in errors)


def test_build_continuity_links_references_neighbors():
    first = Shot(
        id=1, scene_id=1, shot_number=1,
        shot_type="Medium", camera_angle="Eye Level", lens="50mm",
        camera_movement="Static", duration=5, characters=["JANE"],
        action="JANE looks up.", visual_description="Medium shot.",
        continuity_notes="",
    )
    second = Shot(
        id=2, scene_id=1, shot_number=2,
        shot_type="Close-Up", camera_angle="Eye Level", lens="85mm",
        camera_movement="Static", duration=4, characters=["JANE"],
        action="JANE reacts.", visual_description="Close-up.",
        continuity_notes="",
    )
    shot_service.build_continuity_links([first, second], scene_number=3)
    assert "Scene 03 - Shot 01" in second.continuity_notes
    assert "JANE" in second.continuity_notes
    # The first shot has no predecessor, so it gains no auto link.
    assert "[auto]" not in first.continuity_notes


def _session():
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def test_effective_constraints_merges_project_and_scene():
    with _session() as session:
        shot_service.set_constraints(
            session,
            project_id=1,
            scene_id=None,
            data=ProductionConstraints(
                camera_movement_allowed=[CameraMovement.STATIC],
                high_angle_possible=True,
                available_lenses=["50mm", "85mm"],
            ),
        )
        shot_service.set_constraints(
            session,
            project_id=1,
            scene_id=2,
            data=ProductionConstraints(
                camera_movement_allowed=[CameraMovement.PAN],
                available_lenses=["85mm"],
            ),
        )
        merged = shot_service.effective_constraints(session, 1, scene_id=2)
    assert merged["available_lenses"] == ["85mm"]  # scene override wins per-field
    assert merged["high_angle_possible"] is True  # project default preserved
    assert [CameraMovement(v) for v in merged["camera_movement_allowed"]] == [
        CameraMovement.PAN
    ]


def test_effective_constraints_without_rows_uses_defaults():
    with _session() as session:
        merged = shot_service.effective_constraints(session, 1, scene_id=2)
    assert merged["camera_movement_allowed"] == ["Static"]
    assert merged["available_lenses"] == ["50mm"]
    assert merged["high_angle_possible"] is False