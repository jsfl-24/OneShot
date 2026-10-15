"""Tests for the shot generation prompt content and scene context derivation."""

import json
from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine

from oneshot.ai import shot_generator
from oneshot.ai.prompts import SHOT_GENERATION_PROMPT
from oneshot.db_models import Scene
from oneshot.services import shot_service

FIXTURES = Path(__file__).parent / "fixtures"
SHOTS = json.loads((FIXTURES / "sample_shots.json").read_text(encoding="utf-8"))


def test_shot_generation_prompt_contains_required_markers():
    for marker in (
        "context",
        "first_scene",
        "location_changed",
        "new_characters",
        "establishing",
        "Extreme Close-Up",
        "Close-Up",
    ):
        assert marker in SHOT_GENERATION_PROMPT, f"missing marker: {marker}"
    lowered = SHOT_GENERATION_PROMPT.lower()
    assert "plain" in lowered
    assert "natural english" in lowered


def _session():
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def _scene(**overrides):
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


def test_build_scene_context_first_scene():
    with _session() as session:
        scene = _scene()
        session.add(scene)
        session.commit()
        context = shot_service.build_scene_context(session, scene)
    assert context["first_scene"] is True
    assert context["location_changed"] is False
    assert context["new_characters"] == ["JANE"]


def test_build_scene_context_location_changed():
    with _session() as session:
        first = _scene(scene_number=1, location="COFFEE SHOP", characters=["JANE"])
        second = _scene(
            scene_number=2,
            heading="EXT. STREET - NIGHT",
            location="STREET",
            characters=["JANE"],
        )
        session.add_all([first, second])
        session.commit()
        context = shot_service.build_scene_context(session, second)
    assert context["first_scene"] is False
    assert context["location_changed"] is True
    assert context["new_characters"] == []


def test_build_scene_context_same_location_normalized():
    with _session() as session:
        first = _scene(scene_number=1, location="COFFEE SHOP")
        second = _scene(scene_number=2, location="  coffee   shop ")
        session.add_all([first, second])
        session.commit()
        context = shot_service.build_scene_context(session, second)
    assert context["first_scene"] is False
    assert context["location_changed"] is False


def test_build_scene_context_detects_new_characters_across_scenes():
    with _session() as session:
        one = _scene(scene_number=1, characters=["JANE", "MARK"])
        two = _scene(scene_number=2, characters=["jane", "BOB"])
        three = _scene(scene_number=3, characters=["Bob", "MARK"])
        session.add_all([one, two, three])
        session.commit()
        assert shot_service.build_scene_context(session, one)["new_characters"] == [
            "JANE",
            "MARK",
        ]
        assert shot_service.build_scene_context(session, two)["new_characters"] == ["BOB"]
        assert shot_service.build_scene_context(session, three)["new_characters"] == []


def _upload(client):
    project = client.post("/projects", json={"name": "P"}).json()
    with open(FIXTURES / "sample_screenplay.txt", "rb") as fh:
        upload = client.post(
            f"/screenplays/projects/{project['id']}/upload",
            files={"file": ("sample.txt", fh, "text/plain")},
        ).json()
    return upload


async def test_api_prompt_includes_first_scene_context(client, monkeypatch):
    captured: dict[str, str] = {}

    async def fake_generate(prompt, **kwargs):
        captured["prompt"] = prompt
        return json.dumps(SHOTS)

    monkeypatch.setattr(shot_generator, "generate", fake_generate)

    upload = _upload(client)
    scenes = client.get(f"/screenplays/{upload['id']}/scenes").json()["scenes"]
    response = client.post("/shots/generate", json={"scene_id": scenes[0]["id"]})
    assert response.status_code == 200
    assert '"first_scene": true' in captured["prompt"]
    assert '"new_characters"' in captured["prompt"]
