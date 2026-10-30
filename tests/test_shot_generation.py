"""Unit tests for the shot generation AI module."""

import json
from pathlib import Path

import pytest

from oneshot.ai import shot_generator
from oneshot.schemas import AIShotData, ShotType

FIXTURES = Path(__file__).parent / "fixtures"
SCENE = json.loads((FIXTURES / "sample_analyzed_scene.json").read_text(encoding="utf-8"))
SHOTS = json.loads((FIXTURES / "sample_shots.json").read_text(encoding="utf-8"))
CONSTRAINTS = {
    "camera_movement_allowed": ["Static"],
    "high_angle_possible": False,
    "low_angle_possible": True,
    "available_lenses": ["50mm"],
}

# Exact shape of the LiteRT / Gemma 4 E2B failure: the model echoed the JSON
# Schema it was given instead of generating shots.
SCHEMA_ECHO = {
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
        },
    },
}


async def test_generate_shots_returns_validated_data(monkeypatch):
    async def fake_generate(prompt, **kwargs):
        assert kwargs["json_schema"]["items"]["properties"]["shot_type"]["enum"]
        return json.dumps(SHOTS)

    monkeypatch.setattr(shot_generator, "generate", fake_generate)
    shots = await shot_generator.generate_shots(SCENE, CONSTRAINTS)
    assert len(shots) == 3
    assert all(isinstance(s, AIShotData) for s in shots)
    assert shots[0].shot_type is ShotType.WIDE
    assert shots[0].characters == ["JANE", "MARK"]


async def test_generate_shots_rejects_invalid_json(monkeypatch):
    async def fake_generate(prompt, **kwargs):
        return "not json"

    monkeypatch.setattr(shot_generator, "generate", fake_generate)
    with pytest.raises(ValueError, match="invalid JSON"):
        await shot_generator.generate_shots(SCENE, CONSTRAINTS)


async def test_generate_shots_rejects_non_list(monkeypatch):
    async def fake_generate(prompt, **kwargs):
        return json.dumps({"shots": "oops"})

    monkeypatch.setattr(shot_generator, "generate", fake_generate)
    with pytest.raises(ValueError, match="non-list"):
        await shot_generator.generate_shots(SCENE, CONSTRAINTS)


async def test_generate_shots_unwraps_items_envelope(monkeypatch):
    async def fake_generate(prompt, **kwargs):
        return json.dumps({"type": "array", "items": SHOTS})

    monkeypatch.setattr(shot_generator, "generate", fake_generate)
    shots = await shot_generator.generate_shots(SCENE, CONSTRAINTS)
    assert len(shots) == 3
    assert all(isinstance(s, AIShotData) for s in shots)
    assert shots[0].shot_type is ShotType.WIDE


async def test_generate_shots_rejects_items_envelope_without_list(monkeypatch):
    async def fake_generate(prompt, **kwargs):
        return json.dumps({"type": "array"})

    monkeypatch.setattr(shot_generator, "generate", fake_generate)
    with pytest.raises(ValueError, match="non-list"):
        await shot_generator.generate_shots(SCENE, CONSTRAINTS)


async def test_generate_shots_rejects_invalid_enum(monkeypatch):
    bad = dict(SHOTS[0], shot_type="MCU")
    async def fake_generate(prompt, **kwargs):
        return json.dumps([bad])

    monkeypatch.setattr(shot_generator, "generate", fake_generate)
    with pytest.raises(ValueError, match="Shot 1 failed validation"):
        await shot_generator.generate_shots(SCENE, CONSTRAINTS)


async def test_generate_shots_alias_does_not_relax_value_validation(monkeypatch):
    aliased = {("type" if k == "shot_type" else k): v for k, v in SHOTS[0].items()}
    aliased["camera_angle"] = "Bogus Angle"

    async def fake_generate(prompt, **kwargs):
        return json.dumps([aliased])

    monkeypatch.setattr(shot_generator, "generate", fake_generate)
    with pytest.raises(ValueError, match="validation error"):
        await shot_generator.generate_shots(SCENE, CONSTRAINTS)


async def test_generate_shots_forwards_provider(monkeypatch):
    seen = {}

    async def fake_generate(prompt, **kwargs):
        seen.update(kwargs)
        return json.dumps(SHOTS)

    monkeypatch.setattr(shot_generator, "generate", fake_generate)
    await shot_generator.generate_shots(SCENE, CONSTRAINTS, provider="ollama")
    assert seen["provider"] == "ollama"


async def test_generate_shots_rejects_schema_echo_item(monkeypatch):
    async def fake_generate(prompt, **kwargs):
        return json.dumps([SCHEMA_ECHO])

    monkeypatch.setattr(shot_generator, "generate", fake_generate)
    with pytest.raises(ValueError, match="JSON Schema definition"):
        await shot_generator.generate_shots(SCENE, CONSTRAINTS)


async def test_generate_shots_fails_when_echo_mixed_with_valid_shots(monkeypatch):
    async def fake_generate(prompt, **kwargs):
        return json.dumps([SCHEMA_ECHO, SHOTS[0]])

    monkeypatch.setattr(shot_generator, "generate", fake_generate)
    with pytest.raises(ValueError, match="JSON Schema definition"):
        await shot_generator.generate_shots(SCENE, CONSTRAINTS)


async def test_generate_shots_aliases_type_key(monkeypatch):
    aliased = {("type" if k == "shot_type" else k): v for k, v in SHOTS[0].items()}

    async def fake_generate(prompt, **kwargs):
        return json.dumps([aliased])

    monkeypatch.setattr(shot_generator, "generate", fake_generate)
    shots = await shot_generator.generate_shots(SCENE, CONSTRAINTS)
    assert len(shots) == 1
    assert shots[0].shot_type is ShotType.WIDE