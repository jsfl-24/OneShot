"""Scene analysis and LLM-based scene detection service."""

from typing import Any

from sqlmodel import Session, select

from oneshot.ai.scene_analyzer import analyze_scene as analyze_scene_ai
from oneshot.ai.scene_detector_llm import detect_scenes as detect_scenes_llm
from oneshot.db_models import Scene, Screenplay
from oneshot.parsers.scene_detector import parse_heading as parse_heading_re
from oneshot.services.errors import NotFoundError


def get_scene(scene_id: int, session: Session) -> Scene | None:
    return session.get(Scene, scene_id)


def list_scenes(screenplay_id: int, session: Session) -> list[Scene]:
    statement = (
        select(Scene)
        .where(Scene.screenplay_id == screenplay_id)
        .order_by(Scene.scene_number)
    )
    return list(session.exec(statement).all())


def to_dict(scene: Scene) -> dict[str, Any]:
    return {
        "id": scene.id,
        "screenplay_id": scene.screenplay_id,
        "scene_number": scene.scene_number,
        "heading": scene.heading,
        "location": scene.location,
        "time_of_day": scene.time_of_day,
        "raw_text": scene.raw_text,
        "characters": list(scene.characters or []),
        "actions": list(scene.actions or []),
        "dialogue": list(scene.dialogue or []),
        "narrative_context": scene.narrative_context,
        "analyzed": scene.analyzed,
    }


async def analyze_scene(
    scene_id: int,
    session: Session,
    provider: str | None = None,
) -> Scene:
    """Run LLM analysis on a scene and persist the structured result."""
    scene = get_scene(scene_id, session)
    if scene is None:
        raise NotFoundError(f"Scene {scene_id} not found")

    result = await analyze_scene_ai(scene.raw_text, provider=provider)
    scene.characters = list(result.characters)
    scene.actions = list(result.actions)
    scene.dialogue = list(result.dialogue)
    scene.narrative_context = result.narrative_context
    scene.analyzed = True
    session.add(scene)
    session.commit()
    session.refresh(scene)
    return scene


def _normalize_heading(heading: str) -> str:
    return heading.upper().replace(".", "").strip()


def _is_valid_heading(heading: str) -> bool:
    """Check if a heading looks like a real scene heading (INT./EXT. prefix + dash)."""
    upper = heading.upper().strip()
    has_prefix = any(upper.startswith(p) for p in ("INT", "EXT", "I/E", "I.E"))
    has_dash = " - " in upper
    return has_prefix and has_dash


def _text_overlap(a: str, b: str) -> bool:
    """Check if two raw texts overlap significantly."""
    a_lines = set(a.strip().splitlines())
    b_lines = set(b.strip().splitlines())
    if not a_lines or not b_lines:
        return False
    overlap = a_lines & b_lines
    return len(overlap) / min(len(a_lines), len(b_lines)) > 0.7


async def detect_scenes_llm_and_merge(
    screenplay_id: int,
    session: Session,
    provider: str | None = None,
) -> list[Scene]:
    """Run LLM scene detection, merge with regex-detected scenes, persist."""
    screenplay = session.get(Screenplay, screenplay_id)
    if screenplay is None:
        raise NotFoundError(f"Screenplay {screenplay_id} not found")

    detections = await detect_scenes_llm(screenplay.extracted_text, provider=provider)
    lines = screenplay.extracted_text.splitlines()

    scenes = list_scenes(screenplay_id, session)
    existing_headings = {_normalize_heading(s.heading) for s in scenes}
    existing_raw = {s.raw_text for s in scenes}

    new_scenes: list[dict] = []
    for det in sorted(detections, key=lambda d: d.get("line_number", 0)):
        heading = det.get("heading", "").strip()
        if not heading or not _is_valid_heading(heading):
            continue

        if det.get("type") == "correction":
            original = det.get("original") or ""
            for scene in scenes:
                if original and _normalize_heading(original) == _normalize_heading(scene.heading):
                    parsed = parse_heading_re(heading) or {"location": heading, "time_of_day": None}
                    scene.heading = heading
                    scene.location = parsed["location"]
                    scene.time_of_day = parsed["time_of_day"]
                    session.add(scene)
            continue

        if _normalize_heading(heading) in existing_headings:
            continue

        start = det["line_number"] - 1
        end = start + 1
        for other in detections:
            other_start = other.get("line_number", 0) - 1
            if start < other_start < end or other_start == start:
                continue
            if other_start > start:
                end = other_start
                break

        raw_text = "\n".join(lines[start:end]).strip()
        if not raw_text or raw_text in existing_raw:
            continue

        if any(_text_overlap(raw_text, existing) for existing in existing_raw):
            continue

        parsed = parse_heading_re(heading) or {"location": heading, "time_of_day": None}
        new_scenes.append(
            {
                "heading": heading,
                "location": parsed["location"],
                "time_of_day": parsed["time_of_day"],
                "raw_text": raw_text,
            }
        )
        existing_headings.add(_normalize_heading(heading))
        existing_raw.add(raw_text)

    for data in new_scenes:
        scenes.append(
            Scene(
                screenplay_id=screenplay_id,
                project_id=screenplay.project_id,
                scene_number=0,
                **data,
            )
        )

    text = screenplay.extracted_text
    scenes.sort(key=lambda s: _document_position(s, text))

    for number, scene in enumerate(scenes, start=1):
        scene.scene_number = number
        session.add(scene)

    session.commit()
    for scene in scenes:
        session.refresh(scene)
    return scenes


def _document_position(scene: Scene, text: str) -> int:
    first_line = scene.raw_text.strip().splitlines()[0] if scene.raw_text.strip() else ""
    return text.find(first_line) if first_line else 0