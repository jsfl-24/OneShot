"""Tests for the Qdrant-backed knowledge vector store (local file mode, no network)."""

import uuid
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest

import oneshot.rag.store as store_module
from oneshot.config import settings
from oneshot.rag.store import (
    CollectionMismatchError,
    KnowledgePoint,
    VectorStoreError,
    open_store,
    point_uuid,
)

DIM = 8


def _vector(seed: int, dim: int = DIM) -> list[float]:
    return [float((seed + offset) % 7 + 1) for offset in range(dim)]


def _point(chunk_id: str, seed: int, *, dim: int = DIM, **payload) -> KnowledgePoint:
    return KnowledgePoint(
        chunk_id=chunk_id,
        qdrant_id=point_uuid(chunk_id),
        vector=_vector(seed, dim),
        payload={"chunk_id": chunk_id, **payload},
    )


@contextmanager
def _opened_store(**kwargs):
    store = open_store(**kwargs)
    try:
        yield store
    finally:
        store.close()


def test_local_store_persists_points_across_reopen():
    chunk_ids = ["shot_type:persistence-a", "lens:persistence-b"]

    with _opened_store() as store:
        store.ensure_collection(DIM)
        upserted = store.upsert_points(
            [
                _point(chunk_ids[0], 1, category="shot_type"),
                _point(chunk_ids[1], 2, category="lens"),
            ]
        )
        assert upserted == 2

    with _opened_store() as store:
        assert store.count() == 2
        payloads = store.scroll_all_payloads()

    assert len(payloads) == 2
    assert {payload["chunk_id"] for payload in payloads} == set(chunk_ids)


def test_second_open_on_same_path_is_locked_out():
    path = Path(settings.RAG_QDRANT_PATH)

    first = open_store()
    try:
        with pytest.raises(VectorStoreError) as excinfo:
            open_store()
    finally:
        first.close()

    message = str(excinfo.value)
    assert "already" in message.lower()
    assert str(path) in message or str(path.resolve()) in message

    with _opened_store() as reopened:
        reopened.ensure_collection(DIM)
        assert reopened.count() == 0


def test_dimension_mismatch_requires_force_recreate():
    with _opened_store() as store:
        store.ensure_collection(DIM)

        with pytest.raises(CollectionMismatchError) as excinfo:
            store.ensure_collection(16)

        assert isinstance(excinfo.value, VectorStoreError)
        message = str(excinfo.value)
        assert str(DIM) in message
        assert "16" in message

        store.ensure_collection(16, force_recreate=True)
        assert store.count() == 0


def test_upsert_is_idempotent_by_deterministic_id():
    point = _point("movement:push-in", 3)

    with _opened_store() as store:
        store.ensure_collection(DIM)
        store.upsert_points([point])
        store.upsert_points([point])

        assert store.count() == 1
        payloads = store.scroll_all_payloads()

    assert [payload["chunk_id"] for payload in payloads] == ["movement:push-in"]


def test_delete_all_empties_collection_and_allows_later_upserts():
    with _opened_store() as store:
        store.ensure_collection(DIM)
        store.upsert_points([_point("lens:wide", 4), _point("lens:macro", 5)])
        assert store.count() == 2

        store.delete_all()
        assert store.count() == 0
        assert store.scroll_all_payloads() == []

        store.upsert_points([_point("lens:telephoto", 6)])
        assert store.count() == 1


def test_point_uuid_is_deterministic_and_distinct():
    first = point_uuid("shot_type:close-up")
    again = point_uuid("shot_type:close-up")
    other = point_uuid("shot_type:wide-shot")

    assert first == again
    assert first != other
    assert uuid.UUID(first)
    assert uuid.UUID(other)


class _FakeQdrantClient:
    def __init__(self, *args, **kwargs):
        self.init_args = args
        self.init_kwargs = kwargs
        self.closed = False

    def get_collections(self):
        return SimpleNamespace(collections=[])

    def collection_exists(self, name):
        return False

    def close(self):
        self.closed = True


def test_http_mode_constructs_client_with_settings_url(monkeypatch):
    created: list[_FakeQdrantClient] = []

    def _factory(*args, **kwargs):
        client = _FakeQdrantClient(*args, **kwargs)
        created.append(client)
        return client

    monkeypatch.setattr(store_module, "QdrantClient", _factory)

    store = open_store(mode="http")
    try:
        assert len(created) == 1
        assert created[0].init_kwargs["url"] == settings.RAG_QDRANT_URL
        assert "path" not in created[0].init_kwargs
        assert store.collection == settings.RAG_COLLECTION
    finally:
        store.close()


def test_invalid_mode_is_rejected():
    with pytest.raises(ValueError):
        open_store(mode="carrier-pigeon")


def test_scroll_all_payloads_pages_through_large_collection():
    total = 300
    chunk_ids = [f"composition:paged-{index:03d}" for index in range(total)]
    points = [_point(chunk_id, index, dim=4) for index, chunk_id in enumerate(chunk_ids)]

    with _opened_store() as store:
        store.ensure_collection(4)
        assert store.upsert_points(points, batch_size=64) == total
        assert store.count() == total
        payloads = store.scroll_all_payloads()

    assert len(payloads) == total
    assert {payload["chunk_id"] for payload in payloads} == set(chunk_ids)
