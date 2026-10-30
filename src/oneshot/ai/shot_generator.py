"""Shot generation using an LLM.

Turns a structured scene + production constraints into a validated shot list.
Only validated ``AIShotData`` objects leave this module; nothing is persisted
here (the service layer owns persistence).
"""

import json
import logging
from typing import Any

from oneshot.ai.json_output import parse_json
from oneshot.ai.llm import generate
from oneshot.ai.prompts import SHOT_GENERATION_PROMPT
from oneshot.config import settings
from oneshot.schemas import AIShotData, CameraAngle, CameraMovement, ShotType

logger = logging.getLogger(__name__)

_SHOT_TYPE_VALUES = frozenset(e.value for e in ShotType)

# Keys a JSON-Schema definition may carry. An item whose keys are a subset of
# these (and that defines "items" or "properties") is the schema being echoed
# back, not a generated shot.
_SCHEMA_KEYS = frozenset(
    {
        "$defs",
        "$id",
        "$schema",
        "additionalProperties",
        "definitions",
        "description",
        "items",
        "maxItems",
        "minItems",
        "properties",
        "required",
        "title",
        "type",
    }
)


def _is_schema_echo(item: dict[str, Any]) -> bool:
    """True when ``item`` is a JSON-Schema definition rather than a shot."""
    keys = set(item)
    return keys <= _SCHEMA_KEYS and bool(keys & {"items", "properties"})


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
    response = await generate(
        prompt,
        provider=provider,
        model=model,
        json_schema=schema,
        max_tokens=settings.SHOT_MAX_TOKENS,
    )

    try:
        data = parse_json(response)
    except json.JSONDecodeError:
        raise ValueError(f"LLM returned invalid JSON: {response}")

    if isinstance(data, dict) and isinstance(data.get("items"), list):
        data = data["items"]

    if not isinstance(data, list):
        raise ValueError(f"LLM returned non-list shot data: {response}")  # noqa: TRY004

    shots: list[AIShotData] = []
    for index, item in enumerate(data, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"Shot {index} is not an object: {item!r}")  # noqa: TRY004
        if _is_schema_echo(item):
            raise ValueError(
                "LLM returned a JSON Schema definition instead of shot data "
                f"(schema echo at item {index}): {item!r}"
            )
        if "shot_type" not in item and item.get("type") in _SHOT_TYPE_VALUES:
            item["shot_type"] = item.pop("type")
        try:
            shots.append(AIShotData.model_validate(item))
        except Exception as exc:  # validation details are worth surfacing
            logger.debug("Raw LLM shot response failed validation: %s", response)
            raise ValueError(f"Shot {index} failed validation: {exc}") from exc
    return shots