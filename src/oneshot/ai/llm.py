"""LLM abstraction layer.

Supports Ollama (primary) and HuggingFace as providers.
Keep this replaceable per spec §4, §9.
"""

import httpx

from oneshot.config import settings


async def generate(prompt: str, model: str | None = None) -> str:
    """Generate text using the configured LLM provider."""
    provider = settings.LLM_PROVIDER

    if provider == "ollama":
        return await _generate_ollama(prompt, model or settings.LLM_MODEL)
    elif provider == "huggingface":
        return await _generate_huggingface(prompt, model)
    else:
        raise ValueError(f"Unknown LLM provider: {provider}")


async def _generate_ollama(prompt: str, model: str) -> str:
    """Generate text using Ollama API."""
    async with httpx.AsyncClient(base_url=settings.OLLAMA_BASE_URL, timeout=120) as client:
        response = await client.post(
            "/api/generate",
            json={"model": model, "prompt": prompt, "stream": False},
        )
        response.raise_for_status()
        return response.json()["response"]


async def _generate_huggingface(prompt: str, model: str | None) -> str:
    """Generate text using HuggingFace Inference API (placeholder)."""
    raise NotImplementedError("HuggingFace provider not yet implemented")
