"""Shot generation, validation, continuity, and constraint service.

Owns the shot-generation flow: constraint merging, LLM call, validation,
persistence, and automatic continuity links between adjacent shots.
"""

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from sqlmodel import Session, select

from oneshot.ai.shot_generator import generate_shots
from oneshot.db_models import (
    ProductionConstraints as ProductionConstraintsModel,
)
from oneshot.db_models import Scene, Shot
from oneshot.schemas import (
    AIShotData,
    CameraAngle,
    CameraMovement,
    ProductionConstraints,
    ShotListResponse,
    ShotStatus,
    ShotType,
    ShotUpdate,
    shot_ref,
)
from oneshot.schemas import (
    Shot as ShotSchema,
)
from oneshot.services import scene_service
from oneshot.services.errors import ConflictError, InvalidDataError, NotFoundError

_EMPTY_CHARACTERS: list[str] = []


# --- Queries ---

def get_shot(shot_id: int, session: Session) -> Shot | None:
    return session.get(Shot, shot_id)


def get_shot_schema(shot_id: int, session: Session) -> ShotSchema | None:
    shot = get_shot(shot_id, session)
    if shot is None:
        return None
    scene = session.get(Scene, shot.scene_id)
    scene_number = scene.scene_number if scene is not None else 0
    return to_schema(shot, scene_number)


def list_shots(scene_id: int, session: Session) -> list[Shot]:
    statement = (
        select(Shot).where(Shot.scene_id == scene_id).order_by(Shot.shot_number)
    )
    return list(session.exec(statement).all())


# --- Constraints ---

def get_constraints(
    session: Session, project_id: int, scene_id: int | None = None
) -> ProductionConstraintsModel | None:
    statement = select(ProductionConstraintsModel).where(
        ProductionConstraintsModel.project_id == project_id
    )
    if scene_id is None:
        statement = statement.where(ProductionConstraintsModel.scene_id.is_(None))
    else:
        statement = statement.where(ProductionConstraintsModel.scene_id == scene_id)
    return session.exec(statement).first()


def set_constraints(
    session: Session,
    project_id: int,
    scene_id: int | None,
    data: ProductionConstraints,
) -> ProductionConstraintsModel:
    """Create/replace constraints; only fields explicitly provided are stored.

    Unset fields stay NULL so they inherit from the level below during merge.
    """
    row = get_constraints(session, project_id, scene_id)
    if row is None:
        row = ProductionConstraintsModel(project_id=project_id, scene_id=scene_id)
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(row, key, value)
    row.updated_at = datetime.now(UTC)
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def _constraints_to_dict(row: ProductionConstraintsModel | None) -> dict:
    if row is None:
        return {}
    fields = (
        "location_constraints",
        "camera_movement_allowed",
        "high_angle_possible",
        "low_angle_possible",
        "available_lenses",
        "equipment_constraints",
        "director_preferences",
        "additional_notes",
    )
    result: dict = {}
    for field in fields:
        value = getattr(row, field)
        if value is None:
            continue  # not set at this level; inherit from the level below
        result[field] = list(value) if isinstance(value, list) else value
    return result


def effective_constraints(
    session: Session, project_id: int, scene_id: int | None = None
) -> dict:
    """Field-level merge: Pydantic defaults -> project row -> per-scene row."""
    constraints = {
        key: value
        for key, value in ProductionConstraints().model_dump().items()
        if value is not None
    }
    constraints.update(_constraints_to_dict(get_constraints(session, project_id)))
    if scene_id is not None:
        constraints.update(_constraints_to_dict(get_constraints(session, project_id, scene_id)))
    return constraints


# --- Validation ---

def validate_shot(
    ai_shot: AIShotData, scene: Scene, constraints: dict
) -> tuple[list[str], list[str]]:
    """Return (hard errors, soft warnings). Hard errors exclude the shot (reported, never silent)."""
    errors: list[str] = []
    warnings: list[str] = []

    if not 1 <= ai_shot.duration <= 120:
        errors.append(f"duration {ai_shot.duration}s out of range (1-120)")

    available = constraints.get("available_lenses")
    if available and ai_shot.lens not in available:
        errors.append(f"lens {ai_shot.lens!r} not in available lenses {available}")

    movements = constraints.get("camera_movement_allowed")
    if movements and ai_shot.camera_movement.value not in movements:
        errors.append(
            f"camera movement {ai_shot.camera_movement.value!r} not allowed {movements}"
        )

    if ai_shot.camera_angle == CameraAngle.HIGH_ANGLE and not constraints.get(
        "high_angle_possible"
    ):
        errors.append("high angle used but high_angle_possible is false")
    if ai_shot.camera_angle == CameraAngle.LOW_ANGLE and not constraints.get(
        "low_angle_possible"
    ):
        errors.append("low angle used but low_angle_possible is false")

    scene_characters = list(scene.characters or [])
    # Only warn when there is analyzer data to check against.
    if scene_characters:
        for name in ai_shot.characters:
            if name not in scene_characters:
                warnings.append(
                    f"shot references character {name!r} not present in the scene analysis"
                )
    return errors, warnings


# --- Serialization ---

def to_schema(shot: Shot, scene_number: int) -> ShotSchema:
    return ShotSchema(
        id=shot.id,
        scene_id=shot.scene_id,
        scene_number=scene_number,
        shot_number=shot.shot_number,
        shot_type=ShotType(shot.shot_type),
        camera_angle=CameraAngle(shot.camera_angle),
        lens=shot.lens,
        camera_movement=CameraMovement(shot.camera_movement),
        duration=shot.duration,
        characters=list(shot.characters or []),
        dialogue=shot.dialogue,
        action=shot.action,
        visual_description=shot.visual_description,
        continuity_notes=shot.continuity_notes,
        director_notes=shot.director_notes,
        status=ShotStatus(shot.status),
        ref=shot_ref(scene_number, shot.shot_number),
    )


# --- Continuity ---

def build_continuity_links(shots: list[Shot], scene_number: int) -> None:
    """Append auto-generated continuity references between adjacent shots."""
    ordered = sorted(shots, key=lambda s: s.shot_number)
    for index in range(1, len(ordered)):
        prev, current = ordered[index - 1], ordered[index]
        shared = set(prev.characters or _EMPTY_CHARACTERS) & set(
            current.characters or _EMPTY_CHARACTERS
        )
        if shared:
            names = ", ".join(sorted(shared))
            note = (
                f"\n[auto] Continuity from {shot_ref(scene_number, prev.shot_number)}: "
                f"preserve eyeline and screen direction for {names}; keep props, "
                "wardrobe, and set dress consistent."
            )
        else:
            note = (
                f"\n[auto] Continuity from {shot_ref(scene_number, prev.shot_number)}: "
                "new subject; keep spatial geography and eyeline consistent "
                "with the previous coverage."
            )
        current.continuity_notes = (current.continuity_notes or "") + note


# --- Scene context ---

def _normalize_name(value: str) -> str:
    return " ".join(value.strip().casefold().split())


def build_scene_context(session: Session, scene: Scene) -> dict:
    """Derive the ``context`` object injected into the shot-generation prompt."""
    previous = session.exec(
        select(Scene)
        .where(
            Scene.screenplay_id == scene.screenplay_id,
            Scene.scene_number < scene.scene_number,
        )
        .order_by(Scene.scene_number.desc())
    ).first()

    first_scene = previous is None
    if previous is None:
        location_changed = False
    else:
        location_changed = _normalize_name(scene.location) != _normalize_name(
            previous.location
        )

    earlier = session.exec(
        select(Scene).where(
            Scene.screenplay_id == scene.screenplay_id,
            Scene.scene_number < scene.scene_number,
        )
    ).all()
    seen = {
        _normalize_name(name)
        for earlier_scene in earlier
        for name in (earlier_scene.characters or [])
    }
    new_characters: list[str] = []
    for name in scene.characters or []:
        key = _normalize_name(name)
        if key in seen:
            continue
        seen.add(key)
        new_characters.append(name)

    return {
        "first_scene": first_scene,
        "location_changed": location_changed,
        "new_characters": new_characters,
    }


# --- Generation ---

def _to_db(ai_shot: AIShotData, scene_id: int) -> Shot:
    return Shot(
        scene_id=scene_id,
        shot_number=0,  # assigned after validation
        shot_type=ai_shot.shot_type.value,
        camera_angle=ai_shot.camera_angle.value,
        lens=ai_shot.lens,
        camera_movement=ai_shot.camera_movement.value,
        duration=ai_shot.duration,
        characters=list(ai_shot.characters),
        dialogue=ai_shot.dialogue,
        action=ai_shot.action,
        visual_description=ai_shot.visual_description,
        continuity_notes=ai_shot.continuity_notes,
        director_notes=ai_shot.director_notes,
        status="draft",
    )


async def generate_shots_for_scene(
    session: Session,
    scene_id: int,
    constraints: ProductionConstraints | None = None,
    provider: str | None = None,
    model: str | None = None,
    replace_existing: bool = False,
) -> ShotListResponse:
    """Generate, validate, and persist shots for one scene. Approved shots are never deleted."""
    scene = session.get(Scene, scene_id)
    if scene is None:
        raise NotFoundError(f"Scene {scene_id} not found")

    existing = list_shots(scene_id, session)
    if existing and not replace_existing:
        raise ConflictError(
            f"Scene {scene_id} already has {len(existing)} shot(s); "
            "pass replace_existing=true to regenerate"
        )

    approved = [s for s in existing if s.status == "approved"]
    drafts = [s for s in existing if s.status != "approved"]
    if replace_existing and drafts:
        for shot in drafts:
            session.delete(shot)
    session.flush()

    effective = effective_constraints(session, scene.project_id, scene_id)
    if constraints is not None:
        effective.update(
            {
                key: value
                for key, value in constraints.model_dump().items()
                if value is not None
            }
        )

    payload = scene_service.to_dict(scene)
    payload["context"] = build_scene_context(session, scene)
    generated = await generate_shots(payload, effective, provider=provider, model=model)

    warnings: list[str] = []
    new_shots: list[Shot] = []
    for index, ai_shot in enumerate(generated, start=1):
        hard_errors, soft = validate_shot(ai_shot, scene, effective)
        if hard_errors:
            # Surface, never silently discard: report why the shot was rejected.
            warnings.append(f"Shot {index} rejected: {'; '.join(hard_errors)}")
            continue
        warnings.extend(f"Shot {index}: {message}" for message in soft)
        new_shots.append(_to_db(ai_shot, scene_id))

    first_number = max((s.shot_number for s in approved), default=0)
    for number, shot in enumerate(new_shots, start=first_number + 1):
        shot.shot_number = number
    for shot in new_shots:
        session.add(shot)
    session.flush()

    ordered = list(approved) + list(new_shots)
    ordered.sort(key=lambda s: s.shot_number)
    build_continuity_links(ordered, scene.scene_number)
    session.commit()
    for shot in ordered:
        session.refresh(shot)

    return ShotListResponse(
        shots=[to_schema(shot, scene.scene_number) for shot in ordered],
        scene_id=scene.id,
        scene_number=scene.scene_number,
        scene_heading=scene.heading,
        warnings=warnings,
    )


async def generate_shots_for_screenplay(
    session: Session,
    screenplay_id: int,
    constraints: ProductionConstraints | None = None,
    provider: str | None = None,
    model: str | None = None,
    replace_existing: bool = False,
    on_progress: Callable[[dict], Awaitable[None]] | None = None,
) -> list[ShotListResponse]:
    """Generate shots for every scene in a screenplay. Returns per-scene plan results."""
    scenes = scene_service.list_scenes(screenplay_id, session)
    total = max(len(scenes), 1)
    results: list[ShotListResponse] = []
    for index, scene in enumerate(scenes, start=1):
        if on_progress is not None:
            await on_progress(
                {
                    "step": "generating_shots",
                    "percent": int(index / total * 100),
                    "detail": f"Generating shots for scene {scene.scene_number}/{total}",
                }
            )
        result = await generate_shots_for_scene(
            session,
            scene.id,
            constraints=constraints,
            provider=provider,
            model=model,
            replace_existing=replace_existing,
        )
        results.append(result)
    return results


# --- Editing, deletion, reordering, approval ---

_AUTO_CONTINUITY_MARKER = "[auto]"


def _structural_errors(shot: Shot) -> list[str]:
    """Data-integrity problems that make a shot invalid regardless of constraints."""
    errors: list[str] = []
    if not (shot.lens or "").strip():
        errors.append("lens must not be empty")
    if not 1 <= shot.duration <= 120:
        errors.append(f"duration {shot.duration}s out of range (1-120)")
    if not (shot.action or "").strip():
        errors.append("action must not be empty")
    if not (shot.visual_description or "").strip():
        errors.append("visual_description must not be empty")
    return errors


def _constraint_errors(shot: Shot, scene: Scene, session: Session) -> list[str]:
    """Cinematic/constraint violations for a persisted shot (reuses validate_shot)."""
    candidate = AIShotData(
        shot_type=ShotType(shot.shot_type),
        camera_angle=CameraAngle(shot.camera_angle),
        lens=shot.lens,
        camera_movement=CameraMovement(shot.camera_movement),
        duration=shot.duration,
        characters=list(shot.characters or []),
        dialogue=shot.dialogue,
        action=shot.action,
        visual_description=shot.visual_description,
        continuity_notes=shot.continuity_notes,
        director_notes=shot.director_notes,
    )
    effective = effective_constraints(session, scene.project_id, scene.id)
    hard_errors, _ = validate_shot(candidate, scene, effective)
    return hard_errors


def _strip_auto_continuity(shot: Shot) -> None:
    """Remove previously generated ``[auto]`` notes before rebuilding them."""
    notes = shot.continuity_notes or ""
    marker = notes.find(_AUTO_CONTINUITY_MARKER)
    if marker != -1:
        notes = notes[:marker]
    shot.continuity_notes = notes.strip() or None


def _scene_for_shot(shot: Shot, session: Session) -> Scene:
    scene = session.get(Scene, shot.scene_id)
    if scene is None:
        raise NotFoundError(f"Scene {shot.scene_id} for shot {shot.id} not found")
    return scene


def _rebuild_scene_continuity(shots: list[Shot], scene: Scene, session: Session) -> None:
    """Strip stale auto notes, rebuild them in shot order, and renumber refs implicitly."""
    for shot in shots:
        _strip_auto_continuity(shot)
    ordered = sorted(shots, key=lambda s: s.shot_number)
    build_continuity_links(ordered, scene.scene_number)
    for shot in shots:
        shot.updated_at = datetime.now(UTC)
        session.add(shot)


def _renumber_drafts(shots: list[Shot], session: Session) -> None:
    """Renumber drafts contiguously after the highest approved shot number."""
    approved = [shot for shot in shots if shot.status == "approved"]
    drafts = sorted(
        (shot for shot in shots if shot.status != "approved"),
        key=lambda s: s.shot_number,
    )
    next_number = max((shot.shot_number for shot in approved), default=0) + 1
    for offset, shot in enumerate(drafts):
        shot.shot_number = next_number + offset
        shot.updated_at = datetime.now(UTC)
        session.add(shot)


def update_shot(
    shot_id: int,
    data: ShotUpdate,
    session: Session,
) -> ShotSchema:
    """Partially update editable shot fields; ``status`` changes only via approve."""
    shot = get_shot(shot_id, session)
    if shot is None:
        raise NotFoundError(f"Shot {shot_id} not found")

    changes = data.model_dump(exclude_unset=True)
    changes.pop("status", None)  # approval is a separate, validated operation
    if not changes:
        scene = _scene_for_shot(shot, session)
        return to_schema(shot, scene.scene_number)

    scene = _scene_for_shot(shot, session)
    for key, value in changes.items():
        setattr(shot, key, value)

    structural = _structural_errors(shot)
    if structural:
        session.rollback()
        raise InvalidDataError(f"Shot {shot_id} is invalid: {'; '.join(structural)}")

    conflict = _constraint_errors(shot, scene, session)
    if conflict:
        session.rollback()
        raise ConflictError(
            f"Shot {shot_id} violates production constraints: {'; '.join(conflict)}"
        )

    shot.updated_at = datetime.now(UTC)
    session.add(shot)
    session.commit()
    session.refresh(shot)
    return to_schema(shot, scene.scene_number)


def delete_shot(shot_id: int, session: Session) -> None:
    """Delete a draft shot; approved shots are protected. Renumbers remaining drafts."""
    shot = get_shot(shot_id, session)
    if shot is None:
        raise NotFoundError(f"Shot {shot_id} not found")
    if shot.status == "approved":
        raise ConflictError(f"Shot {shot_id} is approved and cannot be deleted")

    scene = _scene_for_shot(shot, session)
    session.delete(shot)
    session.flush()

    remaining = list_shots(shot.scene_id, session)
    _renumber_drafts(remaining, session)
    _rebuild_scene_continuity(remaining, scene, session)
    session.commit()


def reorder_shots(shot_id: int, shot_ids: list[int], session: Session) -> list[ShotSchema]:
    """Reorder the draft shots of the scene that ``shot_id`` belongs to."""
    anchor = get_shot(shot_id, session)
    if anchor is None:
        raise NotFoundError(f"Shot {shot_id} not found")
    scene = _scene_for_shot(anchor, session)

    if len(shot_ids) != len(set(shot_ids)):
        raise InvalidDataError("shot_ids must not contain duplicates")

    all_shots = list_shots(anchor.scene_id, session)
    by_id = {shot.id: shot for shot in all_shots}

    ordered: list[Shot] = []
    for candidate_id in shot_ids:
        candidate = by_id.get(candidate_id)
        if candidate is None:
            if get_shot(candidate_id, session) is None:
                raise NotFoundError(f"Shot {candidate_id} not found")
            raise InvalidDataError(
                f"Shot {candidate_id} does not belong to scene {anchor.scene_id}"
            )
        if candidate.status == "approved":
            raise InvalidDataError("approved shots cannot be reordered")
        ordered.append(candidate)

    draft_ids = {shot.id for shot in all_shots if shot.status != "approved"}
    if {shot.id for shot in ordered} != draft_ids:
        raise InvalidDataError(
            f"shot_ids must contain every draft shot of scene {anchor.scene_id} exactly once"
        )

    approved = [shot for shot in all_shots if shot.status == "approved"]
    next_number = max((shot.shot_number for shot in approved), default=0) + 1
    for offset, shot in enumerate(ordered):
        shot.shot_number = next_number + offset

    _rebuild_scene_continuity(all_shots, scene, session)
    session.commit()

    result = list_shots(anchor.scene_id, session)
    return [to_schema(shot, scene.scene_number) for shot in result]


def approve_shot(shot_id: int, session: Session) -> ShotSchema:
    """Validate a draft shot against structural rules and constraints, then approve it."""
    shot = get_shot(shot_id, session)
    if shot is None:
        raise NotFoundError(f"Shot {shot_id} not found")
    if shot.status == "approved":
        raise ConflictError(f"Shot {shot_id} is already approved")

    scene = _scene_for_shot(shot, session)
    errors = _structural_errors(shot)
    if not errors:
        errors = _constraint_errors(shot, scene, session)
    if errors:
        raise ConflictError(
            f"Shot {shot_id} cannot be approved: {'; '.join(errors)}"
        )

    shot.status = "approved"
    shot.updated_at = datetime.now(UTC)
    session.add(shot)
    session.commit()
    session.refresh(shot)
    return to_schema(shot, scene.scene_number)