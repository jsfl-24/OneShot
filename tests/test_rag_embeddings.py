"""Tests for the pinned RAG embedding layer (no network: fake HTTP transport)."""

import math

import pytest

from oneshot.ai import llm
from oneshot.config import settings
from oneshot.rag import embeddings

SIGNATURE = "litert/embeddinggemma-300m"
DIMENSION = 768


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class _FakeAsyncClient:
    def __init__(self, handler):
        self._handler = handler

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def post(self, url, **kwargs):
        return self._handler(url, kwargs["json"])


def _vector(first: float) -> list[float]:
    """Return a unit-length vector whose first component is ``first``."""
    rest = math.sqrt(max(0.0, 1.0 - first * first) / (DIMENSION - 1))
    return [first] + [rest] * (DIMENSION - 1)


def _norm(vector):
    return math.sqrt(sum(value * value for value in vector))


@pytest.fixture(autouse=True)
def _pin(monkeypatch):
    """Pin the identity so tests do not depend on environment defaults."""
    monkeypatch.setattr(settings, "EMBEDDING_SIGNATURE", SIGNATURE, raising=False)
    monkeypatch.setattr(settings, "EMBEDDING_DIMENSION", DIMENSION, raising=False)


@pytest.fixture
def fake_service(monkeypatch):
    """Fake the embedding HTTP service behind ``llm._client``."""
    state = {"embedding": [1.0] * DIMENSION, "by_text": {}, "calls": []}

    def handler(url, payload):
        state["calls"].append({"url": url, "payload": payload})
        embedding = state["by_text"].get(payload["input"], state["embedding"])
        return _FakeResponse(
            {
                "object": "embedding",
                "embedding": embedding,
                "dimension": len(embedding),
                "model": "embeddinggemma-300m",
            }
        )

    monkeypatch.setattr(llm, "_client", lambda: _FakeAsyncClient(handler))
    return state


async def test_embed_text_returns_unit_vector(fake_service):
    vector = await embeddings.embed_text("a lighthouse at dusk")

    assert len(vector) == DIMENSION
    assert abs(_norm(vector) - 1.0) < 1e-6
    assert fake_service["calls"] == [
        {
            "url": f"{settings.LITERT_EMBEDDING_URL}/v1/embeddings",
            "payload": {"input": "a lighthouse at dusk", "normalize": False},
        }
    ]


@pytest.mark.parametrize("text", ["", "   ", "\n\t "])
async def test_blank_text_rejected(text):
    with pytest.raises(ValueError, match="blank"):
        await embeddings.embed_text(text)


async def test_wrong_dimension_raises_embedding_model_error(fake_service):
    fake_service["embedding"] = [1.0] * (DIMENSION - 1)

    with pytest.raises(embeddings.EmbeddingModelError) as excinfo:
        await embeddings.embed_text("text")

    message = str(excinfo.value)
    assert str(DIMENSION) in message
    assert str(DIMENSION - 1) in message
    assert SIGNATURE in message
    assert "re-ingest" in message


async def test_empty_vector_rejected(fake_service):
    fake_service["embedding"] = []

    with pytest.raises(RuntimeError, match="empty vector"):
        await embeddings.embed_text("text")


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
async def test_non_finite_values_rejected(fake_service, bad):
    fake_service["embedding"] = [1.0] * (DIMENSION - 1) + [bad]

    with pytest.raises(RuntimeError, match="non-finite") as excinfo:
        await embeddings.embed_text("text")

    assert SIGNATURE in str(excinfo.value)


async def test_embed_texts_preserves_order(fake_service):
    fake_service["by_text"] = {
        "one": _vector(0.1),
        "two": _vector(0.2),
        "three": _vector(0.3),
    }

    vectors = await embeddings.embed_texts(["one", "two", "three"])

    assert len(vectors) == 3
    assert [vector[0] for vector in vectors] == pytest.approx([0.1, 0.2, 0.3])
    for vector in vectors:
        assert len(vector) == DIMENSION
        assert abs(_norm(vector) - 1.0) < 1e-6


async def test_embed_texts_empty_returns_empty_list(fake_service):
    assert await embeddings.embed_texts([]) == []
    assert fake_service["calls"] == []


async def test_embed_texts_single_item_matches_embed_text(fake_service):
    single = await embeddings.embed_text("one")
    batch = await embeddings.embed_texts(["one"])

    assert batch == [single]


@pytest.mark.parametrize("concurrency", [0, -1])
async def test_embed_texts_rejects_non_positive_concurrency(concurrency):
    with pytest.raises(ValueError, match="concurrency"):
        await embeddings.embed_texts(["text"], concurrency=concurrency)


def test_signature_and_dimension_match_settings():
    assert embeddings.signature() == settings.EMBEDDING_SIGNATURE
    assert embeddings.dimension() == settings.EMBEDDING_DIMENSION
