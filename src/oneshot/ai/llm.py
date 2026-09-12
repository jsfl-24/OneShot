"""LLM and embedding abstraction layer.

Supports two providers, selectable per deployment, per environment,
and per request:

- ``ollama`` (local)  -> default, privacy-preserving, used in production.
- ``huggingface`` (online) -> development convenience via Hugging Face
  Inference API; requires ``HF_TOKEN``.

The provider choice is resolved in this order:
1. An explicit ``provider`` argument passed by the caller.
2. The ``LLM_PROVIDER`` / ``EMBEDDING_PROVIDER`` environment setting.

Keep this module the single integration point for model serving (spec
§4, §9). Never call providers directly from routes or services.
"""

import httpx

from oneshot.config import settings

_INFERENCE_TIMEOUT = httpx.Timeout(180.0, connect=10.0)

_SUPPORTED_PROVIDERS = ("ollama", "huggingface")


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=_INFERENCE_TIMEOUT)


def _raise_unknown(provider: str) -> None:
    raise ValueError(
        f"Unknown provider: {provider!r}. Supported providers: {', '.join(_SUPPORTED_PROVIDERS)}"
    )


async def generate(
    prompt: str,
    model: str | None = None,
    provider: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> str:
    """Generate text using the configured or requested LLM provider."""
    provider = provider or settings.LLM_PROVIDER
    if model is None:
        model = settings.HF_LLM_MODEL if provider == "huggingface" else settings.LLM_MODEL
    temperature = settings.LLM_TEMPERATURE if temperature is None else temperature
    max_tokens = settings.LLM_MAX_TOKENS if max_tokens is None else max_tokens

    if provider == "ollama":
        return await _generate_ollama(prompt, model)
    if provider == "huggingface":
        return await _generate_huggingface(prompt, model, temperature, max_tokens)
    _raise_unknown(provider)


async def embed(
    text: str,
    model: str | None = None,
    provider: str | None = None,
) -> list[float]:
    """Generate an embedding vector for ``text`` using the chosen provider."""
    provider = provider or settings.EMBEDDING_PROVIDER
    if model is None:
        model = (
            settings.HF_EMBEDDING_MODEL
            if provider == "huggingface"
            else settings.EMBEDDING_MODEL
        )

    if provider == "ollama":
        return await _embed_ollama(text, model)
    if provider == "huggingface":
        return await _embed_huggingface(text, model)
    _raise_unknown(provider)


async def _generate_ollama(prompt: str, model: str) -> str:
    async with _client() as client:
        response = await client.post(
            f"{settings.OLLAMA_BASE_URL}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": settings.LLM_TEMPERATURE,
                    "num_predict": settings.LLM_MAX_TOKENS,
                },
            },
        )
        response.raise_for_status()
    data = response.json()
    text = data.get("response")
    if not text:
        raise ValueError(f"Ollama returned no text for model {model!r}: {data}")
    return text


async def _generate_huggingface(
    prompt: str, model: str, temperature: float, max_tokens: int
) -> str:
    token = settings.HF_TOKEN
    if not token:
        raise RuntimeError(
            "HF_TOKEN is not set. The Hugging Face online provider requires a token "
            "(set the HF_TOKEN environment variable)."
        )

    async with _client() as client:
        response = await client.post(
            f"{settings.HF_BASE_URL}/models/{model}",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "inputs": prompt,
                "parameters": {
                    "temperature": temperature,
                    "max_new_tokens": max_tokens,
                    "return_full_text": False,
                },
                "options": {"wait_for_model": True},
            },
        )
        response.raise_for_status()
    data = response.json()

    if isinstance(data, list) and data:
        text = data[0].get("generated_text", "")
    elif isinstance(data, dict):
        text = data.get("generated_text", "")
    else:
        raise ValueError(f"Hugging Face returned an unexpected payload: {data}")

    if not text:
        raise ValueError(f"Hugging Face returned no text for model {model!r}: {data}")
    return text


async def _embed_ollama(text: str, model: str) -> list[float]:
    async with _client() as client:
        response = await client.post(
            f"{settings.OLLAMA_BASE_URL}/api/embed",
            json={"model": model, "input": text},
        )
        response.raise_for_status()
    data = response.json()

    if "embeddings" in data:
        vectors = data["embeddings"]
        return list(vectors[0]) if vectors else []
    if "embedding" in data:
        return list(data["embedding"])
    raise ValueError(f"Ollama returned an unexpected embedding payload: {data}")


async def _embed_huggingface(text: str, model: str) -> list[float]:
    token = settings.HF_TOKEN
    if not token:
        raise RuntimeError(
            "HF_TOKEN is not set. The Hugging Face online provider requires a token "
            "(set the HF_TOKEN environment variable)."
        )

    async with _client() as client:
        response = await client.post(
            f"{settings.HF_BASE_URL}/pipeline/feature-extraction/{model}",
            headers={"Authorization": f"Bearer {token}"},
            json={"inputs": text, "options": {"wait_for_model": True}},
        )
        response.raise_for_status()
    data = response.json()

    if isinstance(data, list) and data and isinstance(data[0], (int, float)):
        return [float(x) for x in data]
    raise ValueError(f"Hugging Face returned an unexpected embedding payload: {data}")