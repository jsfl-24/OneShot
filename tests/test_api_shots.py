"""API tests for shot generation and persistence."""

import json
from pathlib import Path

import httpx

from oneshot.ai import shot_generator

FIXTURES = Path(__file__).parent / "fixtures"
SHOTS = json.loads((FIXTURES / "sample_shots.json").read_text(encoding="utf-8"))


def _upload(client, filename="tests/fixtures/sample_screenplay.txt", fname="sample.txt"):
    project = client.post("/projects", json={"name": "P"}).json()
    with open(filename, "rb") as fh:
        upload = client.post(
            f"/screenplays/projects/{project['id']}/upload",
            files={"file": (fname, fh, "text/plain")},
        ).json()
    return project, upload


def _first_scene(client, upload):
    return client.get(f"/screenplays/{upload['id']}/scenes").json()["scenes"][0]


async def _mock_shots(monkeypatch, payload=SHOTS):
    async def fake_generate(prompt, **kwargs):
        return json.dumps(payload)

    monkeypatch.setattr(shot_generator, "generate", fake_generate)


async def test_generate_shots_persists_and_returns_plan(client, monkeypatch):
    await _mock_shots(monkeypatch)
    _, upload = _upload(client)
    scene = _first_scene(client, upload)

    response = client.post("/shots/generate", json={"scene_id": scene["id"]})
    assert response.status_code == 200
    body = response.json()
    assert body["scene_id"] == scene["id"]
    assert body["scene_heading"] == scene["heading"]
    assert len(body["shots"]) == 3
    assert body["warnings"] == []

    shot = body["shots"][0]
    assert shot["shot_number"] == 1
    assert shot["ref"] == "Scene 01 - Shot 01"
    assert shot["status"] == "draft"
    # Auto continuity link referencing the previous shot by number
    assert "Scene 01 - Shot 01" in body["shots"][1]["continuity_notes"]

    persisted = client.get(f"/scenes/{scene['id']}/shots").json()
    assert len(persisted) == 3
    assert persisted[0]["id"] == shot["id"]


async def test_generate_shots_404_on_missing_scene(client, monkeypatch):
    await _mock_shots(monkeypatch)
    response = client.post("/shots/generate", json={"scene_id": 999999})
    assert response.status_code == 404


async def test_generate_shots_conflicts_without_replace(client, monkeypatch):
    await _mock_shots(monkeypatch)
    _, upload = _upload(client)
    scene = _first_scene(client, upload)
    first = client.post("/shots/generate", json={"scene_id": scene["id"]})
    assert first.status_code == 200

    second = client.post("/shots/generate", json={"scene_id": scene["id"]})
    assert second.status_code == 409

    third = client.post(
        "/shots/generate",
        json={"scene_id": scene["id"], "replace_existing": True},
    )
    assert third.status_code == 200
    assert len(third.json()["shots"]) == 3


async def test_generate_shots_502_on_provider_error(client, monkeypatch):
    request = httpx.Request("POST", "http://localhost:11434/api/generate")
    response = httpx.Response(500, request=request)

    async def failing_generate(prompt, **kwargs):
        raise httpx.HTTPStatusError("boom", request=request, response=response)

    monkeypatch.setattr(shot_generator, "generate", failing_generate)
    _, upload = _upload(client)
    scene = _first_scene(client, upload)
    result = client.post("/shots/generate", json={"scene_id": scene["id"]})
    assert result.status_code == 502


async def test_generate_shots_504_on_timeout(client, monkeypatch):
    async def timing_out_generate(prompt, **kwargs):
        raise httpx.ReadTimeout("timed out")

    monkeypatch.setattr(shot_generator, "generate", timing_out_generate)
    _, upload = _upload(client)
    scene = _first_scene(client, upload)
    result = client.post("/shots/generate", json={"scene_id": scene["id"]})
    assert result.status_code == 504
    assert "timed out" in result.json()["detail"]


async def test_generate_shots_reports_rejected_shot(client, monkeypatch):
    bad = dict(SHOTS[0], lens="35mm")  # 35mm not in default "50mm" lenses
    await _mock_shots(monkeypatch, payload=[bad, SHOTS[1]])
    _, upload = _upload(client)
    scene = _first_scene(client, upload)

    response = client.post("/shots/generate", json={"scene_id": scene["id"]})
    assert response.status_code == 200
    body = response.json()
    assert len(body["shots"]) == 1  # violating shot excluded
    assert any("rejected" in warning and "35mm" in warning for warning in body["warnings"])


async def test_generate_shots_respects_inline_constraints(client, monkeypatch):
    shot = dict(SHOTS[0], lens="85mm")
    await _mock_shots(monkeypatch, payload=[shot])
    _, upload = _upload(client)
    scene = _first_scene(client, upload)

    response = client.post(
        "/shots/generate",
        json={"scene_id": scene["id"], "constraints": {"available_lenses": ["85mm"]}},
    )
    assert response.status_code == 200
    assert len(response.json()["shots"]) == 1


async def test_generate_shots_accepts_type_alias_for_shot_type(client, monkeypatch):
    aliased = [
        {("type" if k == "shot_type" else k): v for k, v in shot.items()} for shot in SHOTS
    ]
    await _mock_shots(monkeypatch, payload=aliased)
    _, upload = _upload(client)
    scene = _first_scene(client, upload)

    response = client.post("/shots/generate", json={"scene_id": scene["id"]})
    assert response.status_code == 200
    body = response.json()
    assert body["warnings"] == []
    assert [s["shot_type"] for s in body["shots"]] == [s["shot_type"] for s in SHOTS]

    persisted = client.get(f"/scenes/{scene['id']}/shots").json()
    assert [s["shot_type"] for s in persisted] == ["Wide", "Medium Close-Up", "Medium"]


async def test_batch_generate_shots_for_all_scenes(client, monkeypatch):
    await _mock_shots(monkeypatch)
    _, upload = _upload(client)
    scenes = client.get(f"/screenplays/{upload['id']}/scenes").json()["scenes"]
    response = client.post(f"/screenplays/{upload['id']}/generate-shots", json={})
    assert response.status_code == 200
    plans = response.json()
    assert len(plans) == len(scenes)
    assert all(len(plan["shots"]) == 3 for plan in plans)


async def test_batch_generate_shots_stream_emits_progress(client, monkeypatch):
    await _mock_shots(monkeypatch)
    _, upload = _upload(client)
    response = client.post(f"/screenplays/{upload['id']}/generate-shots-stream", json={})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    body = response.text
    assert "event: progress" in body
    assert "generating_shots" in body
    assert "event: complete" in body


async def test_full_pipeline_can_generate_shots(client, monkeypatch):
    from oneshot.ai import scene_analyzer, scene_detector_llm, screenplay_analyzer

    async def fake_detect(prompt, **kwargs):
        return json.dumps({"scenes": []})

    async def fake_analyze(prompt, **kwargs):
        return json.dumps(
            {
                "characters": ["JANE", "MARK"],
                "actions": ["Action here."],
                "dialogue": [],
                "narrative_context": "Context.",
            }
        )

    async def fake_screenplay_analyze(prompt, **kwargs):
        return json.dumps(
            {
                "one_liner": "A short film.",
                "genre": "Drama",
                "story_abstract": "A dramatic encounter.",
                "characters": ["JANE", "MARK"],
            }
        )

    monkeypatch.setattr(scene_detector_llm, "generate", fake_detect)
    monkeypatch.setattr(scene_analyzer, "generate", fake_analyze)
    monkeypatch.setattr(screenplay_analyzer, "generate", fake_screenplay_analyze)
    await _mock_shots(monkeypatch)

    _, upload = _upload(client)
    response = client.post(
        f"/screenplays/{upload['id']}/full-pipeline", params={"generate_shots": True}
    )
    assert response.status_code == 200
    scenes = response.json()["scenes"]
    assert all(s["analyzed"] for s in scenes)

    total = 0
    for scene in scenes:
        total += len(client.get(f"/scenes/{scene['id']}/shots").json())
    assert total == len(scenes) * 3