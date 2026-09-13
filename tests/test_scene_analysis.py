"""Tests for LLM scene detection and structured scene analysis."""

import json

import pytest

from oneshot.schemas import SceneAnalysisResult

SAMPLE = (
    "INT. COFFEE SHOP - DAY\n"
    "Coffee steam rises.\n"
    "JANE\n"
    "I cannot believe you are late again.\n"
    "\n"
    "EXT. STREET - NIGHT\n"
    "Rain falls hard.\n"
)


async def test_detect_scenes_llm_returns_detections(monkeypatch):
    from oneshot.ai import scene_detector_llm

    async def fake_generate(prompt, **kwargs):
        return json.dumps({"scenes": [{"line_number": 6, "heading": "EXT. STREET - NIGHT", "type": "new"}]})

    monkeypatch.setattr(scene_detector_llm, "generate", fake_generate)
    result = await scene_detector_llm.detect_scenes(SAMPLE)
    assert result[0]["heading"] == "EXT. STREET - NIGHT"
    assert result[0]["type"] == "new"


async def test_analyze_scene_returns_validated_result(monkeypatch):
    from oneshot.ai import scene_analyzer

    async def fake_generate(prompt, **kwargs):
        return json.dumps(
            {
                "characters": ["JANE", "MARK"],
                "actions": ["Coffee steam rises."],
                "dialogue": ["JANE: I cannot believe you are late again."],
                "narrative_context": "Tense mood.",
            }
        )

    monkeypatch.setattr(scene_analyzer, "generate", fake_generate)
    result = await scene_analyzer.analyze_scene(SAMPLE)
    assert isinstance(result, SceneAnalysisResult)
    assert result.characters == ["JANE", "MARK"]


async def test_analyze_scene_rejects_invalid_json(monkeypatch):
    from oneshot.ai import scene_analyzer

    async def fake_generate(prompt, **kwargs):
        return "not json"

    monkeypatch.setattr(scene_analyzer, "generate", fake_generate)
    with pytest.raises(ValueError, match="invalid JSON"):
        await scene_analyzer.analyze_scene(SAMPLE)


def _upload(client, filename="tests/fixtures/sample_screenplay.txt", fname="sample.txt"):
    project = client.post("/projects", json={"name": "P"}).json()
    with open(filename, "rb") as fh:
        upload = client.post(
            f"/screenplays/projects/{project['id']}/upload",
            files={"file": (fname, fh, "text/plain")},
        ).json()
    return project, upload


def test_uploaded_scenes_start_unanalyzed(client):
    _, upload = _upload(client)
    scenes = client.get(f"/screenplays/{upload['id']}/scenes").json()["scenes"]
    assert len(scenes) == 4
    assert all(not s["analyzed"] for s in scenes)
    assert all(s["characters"] == [] for s in scenes)


async def test_analyze_scene_persists(client, monkeypatch):
    from oneshot.ai import scene_analyzer

    async def fake_generate(prompt, **kwargs):
        return json.dumps(
            {
                "characters": ["JANE"],
                "actions": ["Steam rises."],
                "dialogue": [],
                "narrative_context": "Calm.",
            }
        )

    monkeypatch.setattr(scene_analyzer, "generate", fake_generate)

    _, upload = _upload(client)
    scene = client.get(f"/screenplays/{upload['id']}/scenes").json()["scenes"][0]
    response = client.post(f"/scenes/{scene['id']}/analyze")
    assert response.status_code == 200
    body = response.json()
    assert body["analyzed"] is True
    assert body["characters"] == ["JANE"]
    assert body["narrative_context"] == "Calm."

    again = client.get(f"/scenes/{scene['id']}")
    assert again.json()["analyzed"] is True


def test_detect_scenes_endpoint_returns_502_on_provider_error(client, monkeypatch):
    import httpx

    from oneshot.ai import scene_analyzer

    request = httpx.Request("POST", "http://localhost:11434/api/generate")
    response = httpx.Response(404, request=request)

    async def failing_generate(prompt, **kwargs):
        raise httpx.HTTPStatusError("model not found", request=request, response=response)

    monkeypatch.setattr(scene_analyzer, "generate", failing_generate)

    _, upload = _upload(client)
    scene = client.get(f"/screenplays/{upload['id']}/scenes").json()["scenes"][0]
    result = client.post(f"/scenes/{scene['id']}/analyze")
    assert result.status_code == 502


def test_detect_scenes_endpoint_returns_404_on_missing_scene(client):
    result = client.post("/scenes/999999/analyze")
    assert result.status_code == 404


def test_detect_scenes_endpoint_merges_new(client, tmp_path, monkeypatch):
    from oneshot.ai import scene_detector_llm

    custom = (
        "Papers everywhere.\n"
        "JOHN\n"
        "Let's begin.\n"
        "\n"
        "EXT. STREET - NIGHT\n"
        "Rain falls.\n"
    )
    path = tmp_path / "custom.txt"
    path.write_text(custom, encoding="utf-8")

    async def fake_generate(prompt, **kwargs):
        return json.dumps(
            {"scenes": [{"line_number": 1, "heading": "INT. OFFICE - DAY", "type": "new"}]}
        )

    monkeypatch.setattr(scene_detector_llm, "generate", fake_generate)

    project = client.post("/projects", json={"name": "P"}).json()
    with open(path, "rb") as fh:
        upload = client.post(
            f"/screenplays/projects/{project['id']}/upload",
            files={"file": ("custom.txt", fh, "text/plain")},
        ).json()

    response = client.post(f"/screenplays/{upload['id']}/detect-scenes")
    assert response.status_code == 200
    scenes = response.json()["scenes"]
    assert len(scenes) == 2
    assert scenes[0]["heading"] == "INT. OFFICE - DAY"


async def test_detect_scenes_endpoint_corrects_typo(client, monkeypatch):
    from oneshot.ai import scene_detector_llm

    async def fake_generate(prompt, **kwargs):
        return json.dumps(
            {
                "scenes": [
                    {
                        "line_number": 5,
                        "heading": "INT. COFFEE SHOP - DAY",
                        "type": "correction",
                        "original": "INT. COFFEE SHOP - DAY",
                    }
                ]
            }
        )

    monkeypatch.setattr(scene_detector_llm, "generate", fake_generate)

    _, upload = _upload(client)
    response = client.post(f"/screenplays/{upload['id']}/detect-scenes")
    assert response.status_code == 200
    assert len(response.json()["scenes"]) == 4


async def test_full_pipeline_analyzes_all(client, monkeypatch):
    from oneshot.ai import scene_analyzer, scene_detector_llm

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

    monkeypatch.setattr(scene_detector_llm, "generate", fake_detect)
    monkeypatch.setattr(scene_analyzer, "generate", fake_analyze)

    _, upload = _upload(client)
    response = client.post(f"/screenplays/{upload['id']}/full-pipeline")
    assert response.status_code == 200
    scenes = response.json()["scenes"]
    assert len(scenes) == 4
    assert all(s["analyzed"] for s in scenes)
    assert all(s["characters"] == ["JANE", "MARK"] for s in scenes)


async def test_provider_query_param_passed_through(client, monkeypatch):
    from oneshot.ai import scene_detector_llm

    calls = {}

    async def fake_generate(prompt, **kwargs):
        calls.update(kwargs)
        return json.dumps({"scenes": []})

    monkeypatch.setattr(scene_detector_llm, "generate", fake_generate)

    _, upload = _upload(client)
    response = client.post(f"/screenplays/{upload['id']}/detect-scenes?provider=huggingface")
    assert response.status_code == 200
    assert calls["provider"] == "huggingface"