"""Tests for the LLM/embedding abstraction layer (LiteRT-only provider)."""

import json

import httpx
import pytest

from oneshot.ai import llm, shot_generator


def _make_client(handler):
    transport = httpx.MockTransport(handler)
    return httpx.AsyncClient(transport=transport)


@pytest.fixture(autouse=True)
def _patch_client(monkeypatch):
    captured = {}

    def handler(request):
        captured["request"] = request
        captured["url"] = str(request.url)
        captured["headers"] = dict(request.headers)
        captured["body"] = json.loads(request.read().decode())
        return httpx.Response(200, json=captured["default_response"])

    monkeypatch.setattr(llm, "_client", lambda: _make_client(handler))
    return captured


async def test_client_timeout_uses_configured_seconds(monkeypatch):
    monkeypatch.undo()  # restore the real _client replaced by _patch_client
    assert llm._inference_timeout().read == float(llm.settings.LLM_TIMEOUT_SECONDS)

    monkeypatch.setattr(llm.settings, "LLM_TIMEOUT_SECONDS", 42)
    client = llm._client()
    assert client.timeout.read == 42
    assert client.timeout.connect == llm._CONNECT_TIMEOUT


async def test_generate_default_provider_is_litert(monkeypatch, _patch_client):
    monkeypatch.setattr(llm.settings, "LLM_PROVIDER", "litert")
    _patch_client["default_response"] = {
        "choices": [{"message": {"content": "default answer"}}]
    }
    text = await llm.generate("hello")
    assert text == "default answer"
    assert _patch_client["url"].endswith("/v1/chat/completions")
    assert _patch_client["body"]["model"] == "gemma-4-E2B-it"


async def test_generate_litert(monkeypatch, _patch_client):
    _patch_client["default_response"] = {
        "choices": [{"message": {"content": "local answer"}}]
    }
    text = await llm.generate("hello", provider="litert")
    assert text == "local answer"
    assert _patch_client["url"].endswith("/v1/chat/completions")
    assert _patch_client["body"]["messages"][0]["content"] == "hello"
    assert _patch_client["body"]["max_tokens"] == 4096


async def test_generate_litert_uses_default_model(monkeypatch, _patch_client):
    _patch_client["default_response"] = {
        "choices": [{"message": {"content": "ok"}}]
    }
    await llm.generate("hello", provider="litert")
    assert _patch_client["body"]["model"] == "gemma-4-E2B-it"


async def test_generate_litert_empty_response(monkeypatch, _patch_client):
    _patch_client["default_response"] = {
        "choices": [{"message": {"content": ""}}]
    }
    with pytest.raises(ValueError, match="returned no text"):
        await llm.generate("hello", provider="litert")


async def test_embed_litert(_patch_client):
    _patch_client["default_response"] = {
        "embedding": [0.7, 0.8, 0.9],
        "dimension": 3,
        "model": "embeddinggemma-300m",
    }
    vector = await llm.embed("text", provider="litert")
    assert vector == [0.7, 0.8, 0.9]
    assert _patch_client["url"].endswith("/v1/embeddings")
    assert _patch_client["body"]["input"] == "text"


async def test_generate_rejects_unsupported_provider():
    with pytest.raises(ValueError, match="only 'litert'"):
        await llm.generate("hello", provider="gemini")


async def test_embed_rejects_unsupported_provider():
    with pytest.raises(ValueError, match="only 'litert'"):
        await llm.embed("text", provider="gemini")


async def test_generate_shots_caps_max_tokens(monkeypatch):
    captured = {}

    async def fake_generate(prompt, **kwargs):
        captured.update(kwargs)
        return "[]"

    monkeypatch.setattr(shot_generator, "generate", fake_generate)
    shots = await shot_generator.generate_shots({"heading": "INT. ROOM - DAY"})
    assert shots == []
    assert captured["max_tokens"] == shot_generator.settings.SHOT_MAX_TOKENS
