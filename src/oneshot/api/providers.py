"""Provider selection and runtime health-check endpoints."""

import time
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from oneshot.ai import llm
from oneshot.config import settings

router = APIRouter(prefix="/providers", tags=["providers"])

ProviderName = Literal["gemini", "ollama", "huggingface"]


class ProviderUpdate(BaseModel):
    llm_provider: ProviderName | None = None
    embedding_provider: ProviderName | None = None


class ProviderInfo(BaseModel):
    provider: str
    model: str


class ProvidersStatus(BaseModel):
    llm: ProviderInfo
    embeddings: ProviderInfo


class PingResult(BaseModel):
    latency_ms: int | None = None
    error: str | None = None


class PingResponse(BaseModel):
    llm: PingResult
    embeddings: PingResult


def _status() -> ProvidersStatus:
    llm_model = (
        settings.GEMINI_MODEL if settings.LLM_PROVIDER == "gemini" else settings.LLM_MODEL
    )
    emb_model = (
        settings.GEMINI_EMBEDDING_MODEL
        if settings.EMBEDDING_PROVIDER == "gemini"
        else settings.EMBEDDING_MODEL
    )
    return ProvidersStatus(
        llm=ProviderInfo(provider=settings.LLM_PROVIDER, model=llm_model),
        embeddings=ProviderInfo(provider=settings.EMBEDDING_PROVIDER, model=emb_model),
    )


@router.post("", response_model=ProvidersStatus)
async def update_providers(payload: ProviderUpdate):
    """Switch LLM and/or embedding provider at runtime (in-memory)."""
    if payload.llm_provider is not None:
        settings.LLM_PROVIDER = payload.llm_provider
    if payload.embedding_provider is not None:
        settings.EMBEDDING_PROVIDER = payload.embedding_provider
    return _status()


async def _measure(coro) -> PingResult:
    start = time.perf_counter()
    try:
        await coro
    except Exception as exc:  # noqa: BLE001 - report any provider error in the payload
        return PingResult(error=str(exc))
    return PingResult(latency_ms=int((time.perf_counter() - start) * 1000))


@router.post("/ping", response_model=PingResponse)
async def ping():
    """Health-check the currently selected providers and report latency."""
    llm_result = await _measure(llm.generate("Say hello", max_tokens=5))
    embed_result = await _measure(llm.embed("test"))
    return PingResponse(llm=llm_result, embeddings=embed_result)