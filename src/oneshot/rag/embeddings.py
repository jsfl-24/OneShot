"""Pinned embedding identity and validation for RAG.

Vectors in the knowledge collection are only comparable when they come from
the same embedding model and have the same dimension. This module pins that
identity (:func:`signature`, :func:`dimension`) and is the single place that
turns text into validated, L2-normalized vectors.

Changing the embedding model changes the vector space, so a model change
requires an explicit re-ingestion of the knowledge collection. Never mix
vectors produced under different signatures.

The HTTP path to the embedding service stays behind :func:`oneshot.ai.llm.embed`.
"""

import asyncio
import math
from collections.abc import Sequence

from oneshot.ai import llm
from oneshot.config import settings

__all__ = [
    "EmbeddingModelError",
    "dimension",
    "embed_text",
    "embed_texts",
    "signature",
]


class EmbeddingModelError(RuntimeError):
    """Raised when an embedding does not match the pinned identity/dimension."""


def signature() -> str:
    """Return the pinned embedding signature (``provider/model``)."""
    return settings.EMBEDDING_SIGNATURE


def dimension() -> int:
    """Return the pinned embedding dimension."""
    return settings.EMBEDDING_DIMENSION


def _l2_normalize(vector: Sequence[float]) -> list[float]:
    """Return an L2-normalized copy of ``vector``.

    Cosine similarity between two vectors is simply the dot product of their
    unit-length versions, so every stored and queried vector is normalized
    here. The transformation is idempotent: normalizing an already normalized
    vector returns it unchanged up to float error.
    """
    values = [float(value) for value in vector]
    norm = math.sqrt(sum(value * value for value in values))
    if not math.isfinite(norm) or norm == 0.0:
        raise RuntimeError("Cannot L2-normalize a zero-norm embedding vector")
    return [value / norm for value in values]


def _validate_vector(payload: object) -> list[float]:
    """Validate a raw service payload and return it as a flat float list.

    Empty, ragged/non-numeric, and non-finite payloads are rejected; a length
    that disagrees with the pinned dimension raises :class:`EmbeddingModelError`.
    """
    try:
        values = [float(value) for value in payload]  # type: ignore[union-attr]
    except (TypeError, ValueError) as exc:
        raise RuntimeError(
            f"Embedding service returned a ragged or non-numeric vector for "
            f"signature {signature()!r}"
        ) from exc

    if not values:
        raise RuntimeError(
            f"Embedding service returned an empty vector for signature {signature()!r}"
        )
    if not all(math.isfinite(value) for value in values):
        raise RuntimeError(
            f"Embedding service returned non-finite values for signature {signature()!r}"
        )

    expected = dimension()
    actual = len(values)
    if actual != expected:
        raise EmbeddingModelError(
            f"Embedding dimension mismatch for signature {signature()!r}: expected "
            f"{expected} values but the service returned {actual}. The embedding "
            "model has changed; re-ingest the knowledge collection with the current "
            "model and signature before querying."
        )
    return values


async def embed_text(text: str) -> list[float]:
    """Embed one text and return an L2-normalized vector for the pinned model."""
    if not text or not text.strip():
        raise ValueError("Cannot embed blank text")
    vector = _validate_vector(await llm.embed(text))
    return _l2_normalize(vector)


async def embed_texts(
    texts: Sequence[str], *, concurrency: int = 4
) -> list[list[float]]:
    """Embed many texts in input order with bounded concurrency.

    Each item goes through :func:`embed_text`, so validation and the dimension
    pin apply identically to batch and single-text calls.
    """
    if concurrency < 1:
        raise ValueError(f"concurrency must be >= 1, got {concurrency}")
    if not texts:
        return []

    semaphore = asyncio.Semaphore(concurrency)

    async def _embed_one(text: str) -> list[float]:
        async with semaphore:
            return await embed_text(text)

    return list(await asyncio.gather(*(_embed_one(text) for text in texts)))
