"""LLM and embedding abstraction layer.

Supports three providers, selectable per deployment, per environment,
and per request:

- ``gemini`` (online, default) -> Google Generative AI API; requires ``GEMINI_API_KEY``.
- ``ollama`` (local)  -> privacy-preserving, used in production.
- ``huggingface`` (online) -> development convenience via Hugging Face
  Inference API; requires ``HF_TOKEN``.
- ``litert`` (local, on-device) -> Gemma 4 E2B served by the LiteRT LLM
  service; embeddings via the EmbeddingGemma 300M HTTP service.

The provider choice is resolved in this order:
1. An explicit ``provider`` argument passed by the caller.
2. The ``LLM_PROVIDER`` / ``EMBEDDING_PROVIDER`` environment setting.

Keep this module the single integration point for model serving (spec
§4, §9). Never call providers directly from routes or services.
"""

# pyrefly: ignore [missing-import]
import httpx

from oneshot.config import settings

_INFERENCE_TIMEOUT = httpx.Timeout(180.0, connect=10.0)

_SUPPORTED_PROVIDERS = ("gemini", "ollama", "huggingface", "litert")


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
        if provider == "gemini":
            model = settings.GEMINI_MODEL
        elif provider == "huggingface":
            model = settings.HF_LLM_MODEL
        elif provider == "litert":
            model = settings.LITERT_LLM_MODEL
        else:
            model = settings.LLM_MODEL
    temperature = settings.LLM_TEMPERATURE if temperature is None else temperature
    max_tokens = settings.LLM_MAX_TOKENS if max_tokens is None else max_tokens

    if provider == "gemini":
        return await _generate_gemini(prompt, model)
    if provider == "ollama":
        return await _generate_ollama(prompt, model)
    if provider == "huggingface":
        return await _generate_huggingface(prompt, model, temperature, max_tokens)
    if provider == "litert":
        return await _generate_litert(prompt, model, max_tokens)
    _raise_unknown(provider)


async def embed(
    text: str,
    model: str | None = None,
    provider: str | None = None,
) -> list[float]:
    """Generate an embedding vector for ``text`` using the chosen provider."""
    provider = provider or settings.EMBEDDING_PROVIDER
    if model is None:
        if provider == "gemini":
            model = settings.GEMINI_EMBEDDING_MODEL
        elif provider == "huggingface":
            model = settings.HF_EMBEDDING_MODEL
        elif provider == "litert":
            model = settings.LITERT_EMBEDDING_MODEL
        else:
            model = settings.EMBEDDING_MODEL

    if provider == "gemini":
        return await _embed_gemini(text, model)
    if provider == "ollama":
        return await _embed_ollama(text, model)
    if provider == "huggingface":
        return await _embed_huggingface(text, model)
    if provider == "litert":
        return await _embed_litert(text, model)
    _raise_unknown(provider)


async def _generate_gemini(prompt: str, model: str) -> str:
    api_key = settings.GEMINI_API_KEY
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. The Gemini online provider requires a key "
            "(set the GEMINI_API_KEY environment variable)."
        )

    from google import genai

    client = genai.Client(api_key=api_key)
    response = await client.aio.models.generate_content(model=model, contents=prompt)
    text = (response.text or "").strip()
    if not text:
        detail_parts = []
        if response.candidates:
            cand = response.candidates[0]
            detail_parts.append(f"finish_reason={cand.finish_reason}")
            if cand.finish_message:
                detail_parts.append(f"finish_message={cand.finish_message!r}")
            if cand.content and cand.content.parts:
                detail_parts.append(f"parts={len(cand.content.parts)}")
                for index, part in enumerate(cand.content.parts):
                    part_len = len(part.text) if part.text else 0
                    detail_parts.append(f"part[{index}]: thought={part.thought}, text_len={part_len}")
        if response.prompt_feedback:
            detail_parts.append(
                f"block_reason={response.prompt_feedback.block_reason}"
            )
            if response.prompt_feedback.block_reason_message:
                detail_parts.append(
                    f"block_message={response.prompt_feedback.block_reason_message!r}"
                )
        if response.usage_metadata:
            detail_parts.append(
                f"tokens={response.usage_metadata.total_token_count}"
            )
        if not detail_parts:
            detail_parts.append(repr(response))
        raise ValueError(
            f"Gemini returned no text for model {model!r}. "
            + "; ".join(detail_parts)
        )
    return text


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
            f"{settings.HF_BASE_URL}/v1/chat/completions",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
        )
        response.raise_for_status()
    data = response.json()

    try:
        message = data["choices"][0].get("message", {})
        text = (message.get("content") or "").strip()
        if not text:
            text = (message.get("reasoning") or "").strip()
    except (KeyError, IndexError, TypeError):
        raise ValueError(f"Hugging Face returned an unexpected payload: {data}")

    if not text:
        raise ValueError(f"Hugging Face returned no text for model {model!r}: {data}")
    return text


async def _generate_litert(prompt: str, model: str, max_tokens: int) -> str:
    async with _client() as client:
        response = await client.post(
            f"{settings.LITERT_LLM_URL}/v1/chat/completions",
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
            },
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


async def _embed_gemini(text: str, model: str) -> list[float]:
    api_key = settings.GEMINI_API_KEY
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. The Gemini online provider requires a key "
            "(set the GEMINI_API_KEY environment variable)."
        )

    from google import genai

    client = genai.Client(api_key=api_key)
    response = await client.aio.models.embed_content(model=model, contents=text)
    values = response.embeddings[0].values
    if not values:
        raise ValueError(f"Gemini returned no embedding for model {model!r}")
    return list(values)


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
            f"{settings.HF_BASE_URL}/hf-inference/models/{model}/pipeline/feature-extraction",
            headers={"Authorization": f"Bearer {token}"},
            json={"inputs": text, "options": {"wait_for_model": True}},
        )
        response.raise_for_status()
    data = response.json()

    if isinstance(data, list) and data:
        if isinstance(data[0], list):
            return [float(x) for x in data[0]]
        return [float(x) for x in data]
    raise ValueError(f"Hugging Face returned an unexpected embedding payload: {data}")


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