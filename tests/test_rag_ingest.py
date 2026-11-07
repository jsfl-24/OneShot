"""Tests for idempotent knowledge ingestion (deterministic stub embeddings, no network)."""

import hashlib
import math
import threading
from contextlib import contextmanager

import pytest

import oneshot.main as main_module
from oneshot.config import settings
from oneshot.rag import ingest
from oneshot.rag.embeddings import EmbeddingModelError
from oneshot.rag.ingest import ingest_corpus, seed_knowledge_if_needed
from oneshot.rag.knowledge import (
    KnowledgeCategory,
    KnowledgeChunk,
    corpus_checksum,
    load_corpus,
)
from oneshot.rag.store import (
    CollectionMismatchError,
    KnowledgePoint,
    open_store,
    point_uuid,
)


def _extra_chunk() -> KnowledgeChunk:
    return KnowledgeChunk(
        category=KnowledgeCategory.COMPOSITION,
        title="Frame Within Frame Edge Case",
        body="Compose through a foreground opening so the subject sits inside a second frame.",
        tags=["depth"],
        attributes={"depth": "layered"},
    )


def _fake_vector(text: str, dim: int) -> list[float]:
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    raw = [digest[index % len(digest)] / 255.0 for index in range(dim)]
    norm = math.sqrt(sum(value * value for value in raw))
    return [value / norm for value in raw]


class _EmbedStub:
    """Async stand-in for ``oneshot.rag.ingest.embed_texts``."""

    def __init__(self, dim: int = 768):
        self.dim = dim
        self.calls: list[list[str]] = []

    async def __call__(self, texts, *, concurrency=4):
        batch = list(texts)
        self.calls.append(batch)
        return [_fake_vector(text, self.dim) for text in batch]


@contextmanager
def _opened_store(**kwargs):
    store = open_store(**kwargs)
    try:
        yield store
    finally:
        store.close()


@pytest.fixture(autouse=True)
def _autoseed_enabled(monkeypatch):
    monkeypatch.setattr(settings, "RAG_AUTOSEED", True, raising=False)


@pytest.fixture()
def embed_stub(monkeypatch):
    stub = _EmbedStub(dim=settings.EMBEDDING_DIMENSION)
    monkeypatch.setattr(ingest, "embed_texts", stub)
    return stub


async def test_first_ingest_embeds_and_upserts_every_chunk(embed_stub):
    corpus = load_corpus()
    size = len(corpus)

    with _opened_store() as store:
        report = await ingest_corpus(store=store)

        assert report.chunks == size
        assert report.embedded == size
        assert report.upserted == size
        assert report.skipped == 0
        assert report.signature == settings.EMBEDDING_SIGNATURE
        assert report.dimension == settings.EMBEDDING_DIMENSION
        assert report.collection == settings.RAG_COLLECTION
        assert report.corpus_sha == corpus_checksum(corpus)
        assert store.count() == size

    assert len(embed_stub.calls) == 1
    assert len(embed_stub.calls[0]) == size
    assert set(embed_stub.calls[0]) == {chunk.embedding_text for chunk in corpus}


async def test_second_ingest_skips_unchanged_corpus(embed_stub):
    corpus = load_corpus()
    size = len(corpus)

    with _opened_store() as store:
        await ingest_corpus(store=store)
        report = await ingest_corpus(store=store)

        assert report.skipped == size
        assert report.embedded == 0
        assert report.upserted == 0
        assert store.count() == size

    assert len(embed_stub.calls) == 1


async def test_corpus_change_reembeds_everything(monkeypatch, embed_stub):
    corpus = load_corpus()
    new_corpus = [*corpus, _extra_chunk()]
    expected_sha = corpus_checksum(new_corpus)

    with _opened_store() as store:
        await ingest_corpus(store=store)

        monkeypatch.setattr(ingest, "load_corpus", lambda directory=None: new_corpus)
        report = await ingest_corpus(store=store)

        assert report.chunks == len(new_corpus)
        assert report.embedded == len(new_corpus)
        assert report.upserted == len(new_corpus)
        assert report.skipped == 0
        assert report.corpus_sha == expected_sha
        assert store.count() == len(new_corpus)
        payloads = store.scroll_all_payloads()

    assert {payload["corpus_sha"] for payload in payloads} == {expected_sha}


async def test_signature_drift_requires_force(monkeypatch, embed_stub):
    corpus = load_corpus()
    size = len(corpus)
    original_signature = settings.EMBEDDING_SIGNATURE

    with _opened_store() as store:
        await ingest_corpus(store=store)

    monkeypatch.setattr(settings, "EMBEDDING_SIGNATURE", "litert/other-model")

    with _opened_store() as store, pytest.raises(EmbeddingModelError) as excinfo:
        await ingest_corpus(store=store)

    message = str(excinfo.value)
    assert "litert/other-model" in message
    assert "force" in message.lower()

    with _opened_store() as store:
        assert store.count() == size
        payloads = store.scroll_all_payloads()
    assert {payload.get("embedding_signature") for payload in payloads} == {original_signature}

    with _opened_store() as store:
        report = await ingest_corpus(force=True, store=store)

        assert report.embedded == size
        assert report.upserted == size
        assert store.count() == size
        payloads = store.scroll_all_payloads()

    assert {payload.get("embedding_signature") for payload in payloads} == {"litert/other-model"}


async def test_wrong_dimension_embeddings_abort_before_writing(embed_stub):
    embed_stub.dim = 256
    expected = settings.EMBEDDING_DIMENSION

    with _opened_store() as store:
        store.ensure_collection(expected)

        with pytest.raises(EmbeddingModelError) as excinfo:
            await ingest_corpus(store=store)

        message = str(excinfo.value)
        assert str(expected) in message
        assert "256" in message
        assert store.count() == 0


async def test_force_rebuild_preserves_data_until_vectors_validate(embed_stub):
    corpus = load_corpus()
    size = len(corpus)

    with _opened_store() as store:
        await ingest_corpus(store=store)
        assert store.count() == size

        embed_stub.dim = 256
        with pytest.raises(EmbeddingModelError):
            await ingest_corpus(force=True, store=store)

        # The failed force rebuild must not destroy the existing collection.
        assert store.count() == size
        assert len(store.scroll_all_payloads()) == size


async def test_dimension_mismatch_blocks_without_force_and_rebuilds_with_force(
    embed_stub,
):
    corpus = load_corpus()
    size = len(corpus)
    legacy = KnowledgePoint(
        chunk_id="shot_type:legacy",
        qdrant_id=point_uuid("shot_type:legacy"),
        vector=[0.5] * 8,
        payload={"chunk_id": "shot_type:legacy", "embedding_signature": "legacy"},
    )

    with _opened_store() as store:
        store.ensure_collection(8)
        store.upsert_points([legacy])

        with pytest.raises(CollectionMismatchError):
            await ingest_corpus(store=store)
        assert store.count() == 1

        report = await ingest_corpus(force=True, store=store)
        assert report.dimension == settings.EMBEDDING_DIMENSION
        assert report.upserted == size
        assert store.count() == size


async def test_seed_knowledge_if_needed_seeds_once(embed_stub):
    corpus = load_corpus()
    size = len(corpus)

    report = await seed_knowledge_if_needed()

    assert report is not None
    assert report.chunks == size
    assert report.upserted == size
    with _opened_store() as store:
        assert store.count() == size

    call_count = len(embed_stub.calls)
    assert await seed_knowledge_if_needed() is None
    assert len(embed_stub.calls) == call_count


def test_lifespan_schedules_autoseed(monkeypatch):
    seeded = threading.Event()

    async def _stub_seed(*, force=False):
        seeded.set()

    monkeypatch.setattr(main_module, "seed_knowledge_if_needed", _stub_seed, raising=False)
    monkeypatch.setattr(settings, "RAG_AUTOSEED", True, raising=False)

    from fastapi.testclient import TestClient

    from oneshot.main import app

    with TestClient(app):
        assert seeded.wait(10)
        assert app.state.rag_autoseed_task is not None
