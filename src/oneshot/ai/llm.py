"""LLM and embedding abstraction layer (LiteRT only).

All inference happens on-device through the LiteRT services:

- ``litert`` -> Gemma 4 E2B on ``LITERT_LLM_URL`` (OpenAI-compatible chat
  completions); EmbeddingGemma 300M on ``LITERT_EMBEDDING_URL``.

LiteRT is the only inference path; no other provider can be selected. Keep this
module the single integration point for model serving (spec §4, §9). Never call
providers directly from routes or services.
"""

# pyrefly: ignore [missing-import]
import httpx

from oneshot.config import settings

_CONNECT_TIMEOUT = 10.0


def _inference_timeout() -> httpx.Timeout:
    """Read timeout from settings (on-device LiteRT decodes slowly)."""
    return httpx.Timeout(float(settings.LLM_TIMEOUT_SECONDS), connect=_CONNECT_TIMEOUT)


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=_inference_timeout())


async def generate(
    prompt: str,
    model: str | None = None,
    provider: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    json_schema: dict | None = None,
) -> str:
    """Generate text using LiteRT.

    ``temperature`` is retained for API compatibility; the LiteRT payload does
    not send it. ``json_schema`` requests JSON output where supported
    (best-effort; parsing + Pydantic validation remains the enforcement point).
    """
    provider = provider or settings.LLM_PROVIDER
    if provider != "litert":
        raise ValueError(f"Unsupported provider {provider!r}: only 'litert' is supported.")
    if model is None:
        model = settings.LITERT_LLM_MODEL
    max_tokens = settings.LLM_MAX_TOKENS if max_tokens is None else max_tokens

    return await _generate_litert(prompt, model, max_tokens, json_schema)


async def embed(
    text: str,
    model: str | None = None,
    provider: str | None = None,
) -> list[float]:
    """Generate an embedding vector for ``text`` using LiteRT."""
    provider = provider or settings.EMBEDDING_PROVIDER
    if provider != "litert":
        raise ValueError(f"Unsupported provider {provider!r}: only 'litert' is supported.")
    if model is None:
        model = settings.LITERT_EMBEDDING_MODEL

    return await _embed_litert(text, model)


async def _generate_litert(prompt: str, model: str, max_tokens: int, json_schema: dict | None = None) -> str:
    payload: dict = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
    }
    if json_schema is not None:
        payload["response_format"] = {"type": "json_object"}
    async with _client() as client:
        response = await client.post(
            f"{settings.LITERT_LLM_URL}/v1/chat/completions",
            json=payload,
        )
        response.raise_for_status()
    data = response.json()

    try:
        message = data["choices"][0].get("message", {})
        text = (message.get("content") or "").strip()
    except (KeyError, IndexError, TypeError):
        raise ValueError(f"LiteRT returned an unexpected payload: {data}")

    if not text:
        raise ValueError(f"LiteRT returned no text for model {model!r}: {data}")
    return text


async def _embed_litert(text: str, model: str) -> list[float]:
    async with _client() as client:
        response = await client.post(
            f"{settings.LITERT_EMBEDDING_URL}/v1/embeddings",
            json={"input": text, "normalize": False},
        )
        response.raise_for_status()
    data = response.json()

    if "embedding" in data:
        return [float(x) for x in data["embedding"]]
    raise ValueError(f"LiteRT returned an unexpected embedding payload: {data}")
