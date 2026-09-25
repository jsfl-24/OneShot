"""Shot generation using an LLM.

Turns a structured scene + production constraints into a validated shot list.
Only validated ``AIShotData`` objects leave this module; nothing is persisted
here (the service layer owns persistence).
"""

import json
from typing import Any

from oneshot.ai.json_output import parse_json
from oneshot.ai.llm import generate
from oneshot.ai.prompts import SHOT_GENERATION_PROMPT
from oneshot.schemas import AIShotData, CameraAngle, CameraMovement, ShotType


def build_shot_schema() -> dict[str, Any]:
    """Strict JSON schema for the shot list, including exact enum values."""
    return {
        "type": "array",
        "items": {
            "type": "object",
            "required": [
                "shot_type",
                "camera_angle",
                "lens",
                "camera_movement",
                "duration",
                "action",
                "visual_description",
            ],
            "properties": {
                "shot_type": {"type": "string", "enum": [e.value for e in ShotType]},
                "camera_angle": {"type": "string", "enum": [e.value for e in CameraAngle]},
                "lens": {"type": "string"},
                "camera_movement": {
                    "type": "string",
                    "enum": [e.value for e in CameraMovement],
                },
                "duration": {"type": "integer", "minimum": 1, "maximum": 120},
                "characters": {"type": "array", "items": {"type": "string"}},
                "dialogue": {"type": "string"},
                "action": {"type": "string"},
                "visual_description": {"type": "string"},
                "continuity_notes": {"type": "string"},
                "director_notes": {"type": "string"},
            },
        },
    }


async def generate_shots(
    scene: dict,
    constraints: dict | None = None,
    provider: str | None = None,
    model: str | None = None,
) -> list[AIShotData]:
    """Generate and validate a shot list for a scene under production constraints."""
    schema = build_shot_schema()
    prompt = SHOT_GENERATION_PROMPT.format(
        scene_json=json.dumps(scene, indent=2),
        constraints_json=json.dumps(constraints or {}, indent=2),
        schema_json=json.dumps(schema, indent=2),
    )
    response = await generate(prompt, provider=provider, model=model, json_schema=schema)

    try:
        data = parse_json(response)
    except json.JSONDecodeError:
        raise ValueError(f"LLM returned invalid JSON: {response}")

    if not isinstance(data, list):
        raise ValueError(f"LLM returned non-list shot data: {response}")  # noqa: TRY004

    shots: list[AIShotData] = []
    for index, item in enumerate(data, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"Shot {index} is not an object: {item!r}")  # noqa: TRY004
        try:
            shots.append(AIShotData.model_validate(item))
        except Exception as exc:  # validation details are worth surfacing
            raise ValueError(f"Shot {index} failed validation: {exc}") from exc
    return shots