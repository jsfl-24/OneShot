"""Tests for the LLM/embedding abstraction layer (online vs local choice)."""

import json

import httpx
import pytest

from oneshot.ai import llm


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


async def test_generate_ollama_default(monkeypatch, _patch_client):
    _patch_client["default_response"] = {"response": "generated text"}
    text = await llm.generate("hello")
    assert text == "generated text"
    assert _patch_client["url"].endswith("/api/generate")
    assert _patch_client["body"]["prompt"] == "hello"
    assert _patch_client["body"]["model"] == "gemma4:4b"


async def test_generate_ollama_uses_model_override(monkeypatch, _patch_client):
    _patch_client["default_response"] = {"response": "ok"}
    await llm.generate("hi", model="llama3")
    assert _patch_client["body"]["model"] == "llama3"


async def test_generate_huggingface_online(monkeypatch, _patch_client):
    monkeypatch.setattr(llm.settings, "HF_TOKEN", "hf_test_token")
    _patch_client["default_response"] = [{"generated_text": "online answer"}]
    text = await llm.generate("hello", provider="huggingface")
    assert text == "online answer"
    assert "api-inference.huggingface.co/models/" in _patch_client["url"]
    assert _patch_client["headers"]["authorization"] == "Bearer hf_test_token"


async def test_generate_huggingface_missing_token(monkeypatch, _patch_client):
    monkeypatch.setattr(llm.settings, "HF_TOKEN", None)
    with pytest.raises(RuntimeError, match="HF_TOKEN"):
        await llm.generate("hello", provider="huggingface")


async def test_generate_unknown_provider():
    with pytest.raises(ValueError, match="Unknown provider"):
        await llm.generate("hello", provider="claude")


async def test_embed_ollama(_patch_client):
    _patch_client["default_response"] = {"embeddings": [[0.1, 0.2, 0.3]]}
    vector = await llm.embed("text")
    assert vector == [0.1, 0.2, 0.3]
    assert _patch_client["url"].endswith("/api/embed")


async def test_embed_huggingface_online(monkeypatch, _patch_client):
    monkeypatch.setattr(llm.settings, "HF_TOKEN", "hf_test_token")
    _patch_client["default_response"] = [0.4, 0.5, 0.6]
    vector = await llm.embed("text", provider="huggingface")
    assert vector == [0.4, 0.5, 0.6]
    assert "pipeline/feature-extraction/" in _patch_client["url"]
    assert _patch_client["headers"]["authorization"] == "Bearer hf_test_token"


def test_supported_providers_are_exposed():
    assert set(llm._SUPPORTED_PROVIDERS) == {"ollama", "huggingface"}