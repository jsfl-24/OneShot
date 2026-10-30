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


# --- Phase 5: shot editing, deletion, reordering, approval ---


def _generate(client, scene, **overrides):
    payload = {"scene_id": scene["id"], **overrides}
    response = client.post("/shots/generate", json=payload)
    assert response.status_code == 200
    return response.json()


async def test_patch_shot_updates_editable_fields(client, monkeypatch):
    await _mock_shots(monkeypatch)
    _, upload = _upload(client)
    scene = _first_scene(client, upload)
    shot = _generate(client, scene)["shots"][0]

    response = client.patch(
        f"/shots/{shot['id']}",
        json={
            "duration": 9,
            "action": "JANE slides a cold cup across the table.",
            "director_notes": "let the silence sit",
            "status": "approved",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["duration"] == 9
    assert body["action"] == "JANE slides a cold cup across the table."
    assert body["director_notes"] == "let the silence sit"
    assert body["status"] == "draft"  # approval is only via /approve
    assert body["shot_number"] == shot["shot_number"]
    assert body["ref"] == shot["ref"]

    persisted = client.get(f"/shots/{shot['id']}").json()
    assert persisted["duration"] == 9
    assert persisted["status"] == "draft"


async def test_patch_shot_empty_body_is_noop(client, monkeypatch):
    await _mock_shots(monkeypatch)
    _, upload = _upload(client)
    scene = _first_scene(client, upload)
    shot = _generate(client, scene)["shots"][0]

    response = client.patch(f"/shots/{shot['id']}", json={})
    assert response.status_code == 200
    assert response.json()["duration"] == shot["duration"]


async def test_patch_shot_invalid_duration_returns_400(client, monkeypatch):
    await _mock_shots(monkeypatch)
    _, upload = _upload(client)
    scene = _first_scene(client, upload)
    shot = _generate(client, scene)["shots"][0]

    response = client.patch(f"/shots/{shot['id']}", json={"duration": 0})
    assert response.status_code == 400
    assert "duration" in response.json()["detail"]
    # the failed update must not be persisted
    assert client.get(f"/shots/{shot['id']}").json()["duration"] == shot["duration"]


async def test_patch_shot_empty_lens_returns_400(client, monkeypatch):
    await _mock_shots(monkeypatch)
    _, upload = _upload(client)
    scene = _first_scene(client, upload)
    shot = _generate(client, scene)["shots"][0]

    response = client.patch(f"/shots/{shot['id']}", json={"lens": "  "})
    assert response.status_code == 400
    assert "lens" in response.json()["detail"]


async def test_patch_shot_constraint_violation_returns_409(client, monkeypatch):
    await _mock_shots(monkeypatch)
    _, upload = _upload(client)
    scene = _first_scene(client, upload)
    shot = _generate(client, scene)["shots"][0]

    response = client.patch(f"/shots/{shot['id']}", json={"lens": "35mm"})
    assert response.status_code == 409
    assert "35mm" in response.json()["detail"]


async def test_patch_shot_missing_returns_404(client):
    response = client.patch("/shots/999999", json={"duration": 4})
    assert response.status_code == 404


async def test_delete_draft_renumbers_and_rebuilds_continuity(client, monkeypatch):
    await _mock_shots(monkeypatch)
    _, upload = _upload(client)
    scene = _first_scene(client, upload)
    shots = _generate(client, scene)["shots"]

    response = client.delete(f"/shots/{shots[1]['id']}")
    assert response.status_code == 204

    remaining = client.get(f"/scenes/{scene['id']}/shots").json()
    assert [shot["shot_number"] for shot in remaining] == [1, 2]
    assert [shot["ref"] for shot in remaining] == [
        "Scene 01 - Shot 01",
        "Scene 01 - Shot 02",
    ]
    survivor = remaining[1]
    assert "[auto]" in survivor["continuity_notes"]
    assert "Scene 01 - Shot 01" in survivor["continuity_notes"]
    # the deleted shot number must not be referenced anymore
    assert "Shot 03" not in survivor["continuity_notes"]


async def test_delete_approved_shot_is_protected(client, monkeypatch):
    await _mock_shots(monkeypatch)
    _, upload = _upload(client)
    scene = _first_scene(client, upload)
    shots = _generate(client, scene)["shots"]

    assert client.post(f"/shots/{shots[0]['id']}/approve").status_code == 200

    response = client.delete(f"/shots/{shots[0]['id']}")
    assert response.status_code == 409
    assert "approved" in response.json()["detail"]
    assert client.get(f"/shots/{shots[0]['id']}").status_code == 200


async def test_delete_missing_shot_returns_404(client):
    assert client.delete("/shots/999999").status_code == 404


async def test_reorder_drafts_updates_numbers_and_continuity(client, monkeypatch):
    await _mock_shots(monkeypatch)
    _, upload = _upload(client)
    scene = _first_scene(client, upload)
    shots = _generate(client, scene)["shots"]

    reversed_ids = [shots[2]["id"], shots[0]["id"], shots[1]["id"]]
    response = client.put(
        f"/shots/{shots[0]['id']}/reorder", json={"shot_ids": reversed_ids}
    )
    assert response.status_code == 200

    body = response.json()
    assert [shot["id"] for shot in body] == reversed_ids
    assert [shot["shot_number"] for shot in body] == [1, 2, 3]
    assert [shot["ref"] for shot in body] == [
        "Scene 01 - Shot 01",
        "Scene 01 - Shot 02",
        "Scene 01 - Shot 03",
    ]
    # continuity was rebuilt for the new order, not the old one
    assert "[auto]" not in (body[0]["continuity_notes"] or "")
    assert "Scene 01 - Shot 01" in body[1]["continuity_notes"]
    assert "Scene 01 - Shot 02" in body[2]["continuity_notes"]

    persisted = client.get(f"/scenes/{scene['id']}/shots").json()
    assert [shot["id"] for shot in persisted] == reversed_ids


async def test_reorder_preserves_approved_shots(client, monkeypatch):
    await _mock_shots(monkeypatch)
    _, upload = _upload(client)
    scene = _first_scene(client, upload)
    shots = _generate(client, scene)["shots"]

    assert client.post(f"/shots/{shots[0]['id']}/approve").status_code == 200

    response = client.put(
        f"/shots/{shots[1]['id']}/reorder",
        json={"shot_ids": [shots[2]["id"], shots[1]["id"]]},
    )
    assert response.status_code == 200
    body = response.json()
    assert [shot["id"] for shot in body] == [
        shots[0]["id"],
        shots[2]["id"],
        shots[1]["id"],
    ]
    assert body[0]["shot_number"] == 1
    assert body[0]["status"] == "approved"


async def test_reorder_rejects_approved_shot_in_list(client, monkeypatch):
    await _mock_shots(monkeypatch)
    _, upload = _upload(client)
    scene = _first_scene(client, upload)
    shots = _generate(client, scene)["shots"]
    assert client.post(f"/shots/{shots[0]['id']}/approve").status_code == 200

    response = client.put(
        f"/shots/{shots[1]['id']}/reorder",
        json={"shot_ids": [shots[0]["id"], shots[1]["id"]]},
    )
    assert response.status_code == 400
    assert "approved" in response.json()["detail"]


async def test_reorder_rejects_foreign_scene_shot(client, monkeypatch):
    await _mock_shots(monkeypatch)
    _, upload = _upload(client)
    scenes = client.get(f"/screenplays/{upload['id']}/scenes").json()["scenes"]
    first = _generate(client, scenes[0])["shots"]
    second = _generate(client, scenes[1])["shots"]

    response = client.put(
        f"/shots/{first[0]['id']}/reorder",
        json={"shot_ids": [second[0]["id"], first[1]["id"], first[2]["id"]]},
    )
    assert response.status_code == 400
    assert "does not belong" in response.json()["detail"]


async def test_reorder_rejects_incomplete_or_duplicate_lists(client, monkeypatch):
    await _mock_shots(monkeypatch)
    _, upload = _upload(client)
    scene = _first_scene(client, upload)
    shots = _generate(client, scene)["shots"]

    incomplete = client.put(
        f"/shots/{shots[0]['id']}/reorder",
        json={"shot_ids": [shots[0]["id"], shots[1]["id"]]},
    )
    assert incomplete.status_code == 400

    duplicate = client.put(
        f"/shots/{shots[0]['id']}/reorder",
        json={"shot_ids": [shots[0]["id"], shots[0]["id"], shots[1]["id"]]},
    )
    assert duplicate.status_code == 400

    unknown = client.put(
        f"/shots/{shots[0]['id']}/reorder",
        json={"shot_ids": [shots[0]["id"], shots[1]["id"], 999999]},
    )
    assert unknown.status_code == 404


async def test_reorder_missing_anchor_returns_404(client):
    response = client.put("/shots/999999/reorder", json={"shot_ids": []})
    assert response.status_code == 404


async def test_approve_valid_shot(client, monkeypatch):
    await _mock_shots(monkeypatch)
    _, upload = _upload(client)
    scene = _first_scene(client, upload)
    shot = _generate(client, scene)["shots"][0]

    response = client.post(f"/shots/{shot['id']}/approve")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "approved"
    assert client.get(f"/shots/{shot['id']}").json()["status"] == "approved"


async def test_approve_constraint_violation_returns_409(client, monkeypatch):
    await _mock_shots(monkeypatch)
    _, upload = _upload(client)
    project = client.get("/projects").json()[0]
    scene = _first_scene(client, upload)
    shot = _generate(client, scene)["shots"][0]  # Static movement

    # Tighten project constraints so the existing draft is no longer filmable.
    constraints = client.put(
        f"/projects/{project['id']}/constraints",
        json={"camera_movement_allowed": ["Dolly"]},
    )
    assert constraints.status_code == 200

    response = client.post(f"/shots/{shot['id']}/approve")
    assert response.status_code == 409
    assert "camera movement" in response.json()["detail"]
    assert client.get(f"/shots/{shot['id']}").json()["status"] == "draft"


async def test_approve_twice_returns_409(client, monkeypatch):
    await _mock_shots(monkeypatch)
    _, upload = _upload(client)
    scene = _first_scene(client, upload)
    shot = _generate(client, scene)["shots"][0]

    assert client.post(f"/shots/{shot['id']}/approve").status_code == 200
    response = client.post(f"/shots/{shot['id']}/approve")
    assert response.status_code == 409


async def test_approve_missing_shot_returns_404(client):
    assert client.post("/shots/999999/approve").status_code == 404


async def test_shot_editing_workflow_end_to_end(client, monkeypatch):
    await _mock_shots(monkeypatch)
    _, upload = _upload(client)
    scene = _first_scene(client, upload)
    shots = _generate(client, scene)["shots"]
    first, second, third = shots

    edited = client.patch(
        f"/shots/{first['id']}",
        json={"duration": 7, "visual_description": "Wide, warm morning light."},
    )
    assert edited.status_code == 200

    assert client.delete(f"/shots/{third['id']}").status_code == 204

    reordered = client.put(
        f"/shots/{first['id']}/reorder",
        json={"shot_ids": [second["id"], first["id"]]},
    )
    assert reordered.status_code == 200
    assert [shot["id"] for shot in reordered.json()] == [second["id"], first["id"]]
    assert [shot["shot_number"] for shot in reordered.json()] == [1, 2]

    approved = client.post(f"/shots/{second['id']}/approve")
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"

    final = client.get(f"/scenes/{scene['id']}/shots").json()
    assert [shot["id"] for shot in final] == [second["id"], first["id"]]
    assert [shot["ref"] for shot in final] == [
        "Scene 01 - Shot 01",
        "Scene 01 - Shot 02",
    ]
    assert final[0]["status"] == "approved"
    assert final[1]["duration"] == 7
    assert "[auto]" in final[1]["continuity_notes"]