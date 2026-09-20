"""Tests for provider selection and ping endpoints."""

import asyncio

from oneshot.ai import llm
from oneshot.config import settings


async def _fake_ok(*args, **kwargs):
    await asyncio.sleep(0.01)
    return "pong"


async def test_providers_switch_llm(client, monkeypatch):
    monkeypatch.setattr(settings, "LLM_PROVIDER", "gemini")
    monkeypatch.setattr(settings, "EMBEDDING_PROVIDER", "gemini")
    response = client.post(
        "/providers", json={"llm_provider": "ollama"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["llm"]["provider"] == "ollama"
    assert settings.LLM_PROVIDER == "ollama"
    assert body["embeddings"]["provider"] == "gemini"
    assert settings.EMBEDDING_PROVIDER == "gemini"
    assert "model" in body["llm"]


def test_providers_switch_embedding(client, monkeypatch):
    monkeypatch.setattr(settings, "LLM_PROVIDER", "gemini")
    monkeypatch.setattr(settings, "EMBEDDING_PROVIDER", "gemini")
    response = client.post(
        "/providers", json={"embedding_provider": "ollama"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["llm"]["provider"] == "gemini"
    assert body["embeddings"]["provider"] == "ollama"
    assert settings.EMBEDDING_PROVIDER == "ollama"


def test_providers_switch_both_at_once(client, monkeypatch):
    monkeypatch.setattr(settings, "LLM_PROVIDER", "gemini")
    monkeypatch.setattr(settings, "EMBEDDING_PROVIDER", "gemini")
    response = client.post(
        "/providers",
        json={"llm_provider": "huggingface", "embedding_provider": "ollama"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body == {
        "llm": {"provider": "huggingface", "model": settings.LLM_MODEL},
        "embeddings": {"provider": "ollama", "model": settings.EMBEDDING_MODEL},
    }


def test_providers_reject_invalid_provider(client):
    response = client.post("/providers", json={"llm_provider": "claude"})
    assert response.status_code == 422


def test_providers_reject_empty_switch(client, monkeypatch):
    monkeypatch.setattr(settings, "LLM_PROVIDER", "gemini")
    monkeypatch.setattr(settings, "EMBEDDING_PROVIDER", "gemini")
    response = client.post("/providers", json={})
    assert response.status_code == 200
    assert response.json()["llm"]["provider"] == "gemini"


async def test_ping_reports_latency(client, monkeypatch):
    monkeypatch.setattr(llm, "generate", _fake_ok)
    monkeypatch.setattr(llm, "embed", _fake_ok)
    response = client.post("/providers/ping")
    assert response.status_code == 200
    body = response.json()
    assert body["llm"]["latency_ms"] >= 0
    assert body["llm"]["error"] is None
    assert body["embeddings"]["latency_ms"] >= 0


async def test_ping_reports_error_per_provider(client, monkeypatch):
    async def failing(*args, **kwargs):
        raise RuntimeError("provider unreachable")

    monkeypatch.setattr(llm, "generate", failing)
    monkeypatch.setattr(llm, "embed", _fake_ok)
    response = client.post("/providers/ping")
    assert response.status_code == 200
    body = response.json()
    assert body["llm"]["latency_ms"] is None
    assert "provider unreachable" in body["llm"]["error"]
    assert body["embeddings"]["latency_ms"] >= 0
    assert body["embeddings"]["error"] is None