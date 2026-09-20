"""Tests for the LLM/embedding abstraction layer (online vs local choice)."""

import json
import sys
from types import ModuleType

import httpx
import pytest

from oneshot.ai import llm

DEFAULT_GEMINI_MODEL = "gemma-4-26b-a4b-it"
DEFAULT_GEMINI_EMBEDDING_MODEL = "gemini-embedding-2"


class FakeResponse:
    def __init__(self, text, candidates=None):
        self.text = text
        self.candidates = candidates or []
        self.prompt_feedback = None
        self.usage_metadata = None


class FakeCandidate:
    def __init__(self, finish_reason, parts, finish_message=None):
        self.finish_reason = finish_reason
        self.finish_message = finish_message
        self.content = type("Content", (), {"parts": parts})()


class FakePart:
    def __init__(self, text, thought=None):
        self.text = text
        self.thought = thought


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


@pytest.fixture
def _patch_genai(monkeypatch):
    """Fake the `google.genai` SDK (imported lazily inside _generate_gemini)."""
    captured = {}

    class FakeEmbedding:
        def __init__(self, values):
            self.values = values

    class FakeEmbedResponse:
        def __init__(self, embeddings):
            self.embeddings = embeddings

    class FakeModelsAsync:
        async def generate_content(self, model=None, contents=None, **_):
            captured["model"] = model
            captured["contents"] = contents
            default = captured["default_response"]
            if isinstance(default, FakeResponse):
                return default
            return FakeResponse(captured["default_response"])

        async def embed_content(self, model=None, contents=None, **_):
            captured["model"] = model
            captured["contents"] = contents
            return FakeEmbedResponse(
                [FakeEmbedding(captured["default_response"])]
            )

    class FakeAio:
        def __init__(self):
            self.models = FakeModelsAsync()

    class FakeClient:
        def __init__(self, api_key=None):
            captured["api_key"] = api_key
            self.aio = FakeAio()

    fake_genai = ModuleType("google.genai")
    fake_genai.Client = FakeClient
    fake_google = ModuleType("google")
    fake_google.genai = fake_genai

    monkeypatch.setitem(sys.modules, "google", fake_google)
    monkeypatch.setitem(sys.modules, "google.genai", fake_genai)
    return captured


async def test_generate_gemini_online(monkeypatch, _patch_genai):
    monkeypatch.setattr(llm.settings, "GEMINI_API_KEY", "gem_test_key")
    _patch_genai["default_response"] = "gemini answer"
    text = await llm.generate("hello", provider="gemini")
    assert text == "gemini answer"
    assert _patch_genai["model"] == DEFAULT_GEMINI_MODEL
    assert _patch_genai["contents"] == "hello"
    assert _patch_genai["api_key"] == "gem_test_key"


async def test_generate_gemini_uses_model_override(monkeypatch, _patch_genai):
    monkeypatch.setattr(llm.settings, "GEMINI_API_KEY", "gem_test_key")
    _patch_genai["default_response"] = "ok"
    await llm.generate("hi", model="gemma-3-4b-it", provider="gemini")
    assert _patch_genai["model"] == "gemma-3-4b-it"


async def test_generate_gemini_missing_key(monkeypatch, _patch_genai):
    monkeypatch.setattr(llm.settings, "GEMINI_API_KEY", None)
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        await llm.generate("hello", provider="gemini")


async def test_generate_gemini_empty_text_reports_diagnostics(monkeypatch, _patch_genai):
    monkeypatch.setattr(llm.settings, "GEMINI_API_KEY", "gem_test_key")
    _patch_genai["default_response"] = FakeResponse(
        text="",
        candidates=[
            FakeCandidate(
                finish_reason="SAFETY",
                parts=[FakePart("thinking", thought=True), FakePart("", thought=None)],
            )
        ],
    )
    with pytest.raises(ValueError) as excinfo:
        await llm.generate("hello", provider="gemini")
    message = str(excinfo.value)
    assert "Gemini returned no text" in message
    assert "finish_reason=SAFETY" in message
    assert "part[1]: thought=None" in message
    assert "text_len=0" in message


async def test_generate_default_provider_is_gemini(monkeypatch, _patch_genai):
    monkeypatch.setattr(llm.settings, "LLM_PROVIDER", "gemini")
    monkeypatch.setattr(llm.settings, "GEMINI_API_KEY", "gem_test_key")
    _patch_genai["default_response"] = "default answer"
    text = await llm.generate("hello")
    assert text == "default answer"
    assert _patch_genai["model"] == DEFAULT_GEMINI_MODEL


async def test_generate_ollama(monkeypatch, _patch_client):
    _patch_client["default_response"] = {"response": "generated text"}
    text = await llm.generate("hello", provider="ollama")
    assert text == "generated text"
    assert _patch_client["url"].endswith("/api/generate")
    assert _patch_client["body"]["prompt"] == "hello"
    assert _patch_client["body"]["model"] == "gemma4:latest"


async def test_generate_ollama_uses_model_override(monkeypatch, _patch_client):
    _patch_client["default_response"] = {"response": "ok"}
    await llm.generate("hi", model="llama3", provider="ollama")
    assert _patch_client["body"]["model"] == "llama3"


async def test_generate_huggingface_online(monkeypatch, _patch_client):
    monkeypatch.setattr(llm.settings, "HF_TOKEN", "hf_test_token")
    _patch_client["default_response"] = {
        "choices": [{"message": {"content": "online answer"}}]
    }
    text = await llm.generate("hello", provider="huggingface")
    assert text == "online answer"
    assert "https://router.huggingface.co/v1/chat/completions" in _patch_client["url"]
    assert _patch_client["headers"]["authorization"] == "Bearer hf_test_token"
    assert _patch_client["body"]["messages"][0]["content"] == "hello"


async def test_generate_huggingface_falls_back_to_reasoning(monkeypatch, _patch_client):
    monkeypatch.setattr(llm.settings, "HF_TOKEN", "hf_test_token")
    _patch_client["default_response"] = {
        "choices": [{"message": {"content": None, "reasoning": "thinking..."}}]
    }
    text = await llm.generate("hello", provider="huggingface")
    assert text == "thinking..."


async def test_generate_huggingface_missing_token(monkeypatch, _patch_client):
    monkeypatch.setattr(llm.settings, "HF_TOKEN", None)
    with pytest.raises(RuntimeError, match="HF_TOKEN"):
        await llm.generate("hello", provider="huggingface")


async def test_generate_unknown_provider():
    with pytest.raises(ValueError, match="Unknown provider"):
        await llm.generate("hello", provider="claude")


async def test_embed_gemini_online(monkeypatch, _patch_genai):
    monkeypatch.setattr(llm.settings, "GEMINI_API_KEY", "gem_test_key")
    _patch_genai["default_response"] = [0.1, 0.2, 0.3]
    vector = await llm.embed("text", provider="gemini")
    assert vector == [0.1, 0.2, 0.3]
    assert _patch_genai["model"] == DEFAULT_GEMINI_EMBEDDING_MODEL
    assert _patch_genai["contents"] == "text"
    assert _patch_genai["api_key"] == "gem_test_key"


async def test_embed_gemini_missing_key(monkeypatch, _patch_genai):
    monkeypatch.setattr(llm.settings, "GEMINI_API_KEY", None)
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        await llm.embed("text", provider="gemini")


async def test_embed_ollama(_patch_client):
    _patch_client["default_response"] = {"embeddings": [[0.1, 0.2, 0.3]]}
    vector = await llm.embed("text", provider="ollama")
    assert vector == [0.1, 0.2, 0.3]
    assert _patch_client["url"].endswith("/api/embed")


async def test_embed_huggingface_online(monkeypatch, _patch_client):
    monkeypatch.setattr(llm.settings, "HF_TOKEN", "hf_test_token")
    _patch_client["default_response"] = [0.4, 0.5, 0.6]
    vector = await llm.embed("text", provider="huggingface")
    assert vector == [0.4, 0.5, 0.6]
    assert "hf-inference/models/" in _patch_client["url"]
    assert _patch_client["headers"]["authorization"] == "Bearer hf_test_token"


def test_supported_providers_are_exposed():
    assert set(llm._SUPPORTED_PROVIDERS) == {"gemini", "ollama", "huggingface"}