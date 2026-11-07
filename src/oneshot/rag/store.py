"""Qdrant-backed vector store for the cinematic knowledge base.

Local-file mode (the default) keeps vectors on disk under ``data/qdrant`` and
needs no server. HTTP mode points at a Qdrant server instead. Only one process
may hold a local storage folder at a time, so a locked folder is reported as a
clear, actionable error rather than a raw client exception.

Point ids are deterministic UUIDs derived from ``chunk_id``, which makes
re-ingestion an idempotent upsert instead of a duplicate vector build-up.
"""

from __future__ import annotations

import gc
import logging
import shutil
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from qdrant_client import QdrantClient, models

from oneshot.config import settings

logger = logging.getLogger(__name__)

__all__ = [
    "CollectionMismatchError",
    "KnowledgePoint",
    "QdrantStore",
    "VectorStoreError",
    "open_store",
    "point_uuid",
]

# Fixed namespace: changing it would change every point id in the collection.
_UUID_NAMESPACE = uuid.UUID("2f6d3c4a-7b1e-5c88-9d0b-1a4f6e2c8b93")

_SCROLL_PAGE_SIZE = 256
_SCROLL_MAX_POINTS = 10_000
_MISSING_COLLECTION_HINTS = ("not found", "doesn't exist", "does not exist")


class VectorStoreError(RuntimeError):
    """Raised when the underlying vector store cannot be opened or used."""


class CollectionMismatchError(VectorStoreError):
    """Raised when the stored collection was built for a different dimension."""


@dataclass(frozen=True)
class KnowledgePoint:
    """One knowledge chunk ready to be written to the vector store."""

    chunk_id: str
    qdrant_id: str
    vector: list[float]
    payload: dict[str, Any]


def point_uuid(chunk_id: str) -> str:
    """Return the deterministic Qdrant point id for ``chunk_id``."""
    return str(uuid.uuid5(_UUID_NAMESPACE, chunk_id))


def _is_missing_collection(exc: BaseException) -> bool:
    """Return True when ``exc`` reports a collection that does not exist."""
    text = str(exc).lower()
    return any(hint in text for hint in _MISSING_COLLECTION_HINTS)


class QdrantStore:
    """Thin, synchronous wrapper around one Qdrant collection."""

    def __init__(
        self, client: Any, collection: str, *, storage_path: Path | None = None
    ) -> None:
        self._client = client
        self.collection = collection
        self._storage_path = storage_path

    # -- schema ---------------------------------------------------------

    def _get_collection_info(self) -> Any | None:
        """Return the collection info, or None when the collection is missing."""
        try:
            return self._client.get_collection(self.collection)
        except Exception as exc:
            if _is_missing_collection(exc):
                return None
            raise VectorStoreError(
                f"Could not inspect collection {self.collection!r}: {exc}"
            ) from exc

    def _create_collection(self, dimension: int) -> None:
        self._client.create_collection(
            collection_name=self.collection,
            vectors_config=models.VectorParams(
                size=dimension, distance=models.Distance.COSINE
            ),
        )

    def _delete_collection(self) -> None:
        try:
            self._client.delete_collection(self.collection)
        except Exception as exc:
            if not _is_missing_collection(exc):
                raise VectorStoreError(
                    f"Could not delete collection {self.collection!r}: {exc}"
                ) from exc

    def _recreate_collection(self, dimension: int) -> None:
        """Delete the collection and create a fresh one of ``dimension``.

        qdrant-client's local mode keeps the collection's SQLite handle alive
        after ``delete_collection`` on Windows, so the storage folder cannot be
        removed; recreating the same name would then silently reuse the old,
        incompatible vectors. Collecting cycles and removing the folder
        ourselves makes the recreate reliable.
        """
        if self._get_collection_info() is not None:
            self._delete_collection()
            if self._storage_path is not None:
                gc.collect()
                collection_dir = self._storage_path / "collection" / self.collection
                if collection_dir.exists():
                    try:
                        shutil.rmtree(collection_dir)
                    except OSError as exc:
                        raise VectorStoreError(
                            f"Could not rebuild collection {self.collection!r}: the "
                            f"storage folder '{collection_dir}' is still in use."
                        ) from exc
        self._create_collection(dimension)

    def ensure_collection(self, dimension: int, *, force_recreate: bool = False) -> None:
        """Ensure a cosine collection of ``dimension`` exists.

        An existing collection with a different dimension is never reused: it
        is either rebuilt (``force_recreate=True``) or reported as a mismatch.
        With ``force_recreate=True`` the collection is always recreated empty.
        """
        if force_recreate:
            self._recreate_collection(dimension)
            return

        info = self._get_collection_info()
        if info is None:
            self._create_collection(dimension)
            return

        actual = info.config.params.vectors.size
        if actual != dimension:
            raise CollectionMismatchError(
                f"Collection {self.collection!r} stores {actual}-dimensional vectors "
                f"but the current embedding model produces {dimension}-dimensional "
                "vectors. The collection must be rebuilt (force_recreate=True, or "
                "`python -m oneshot.rag.ingest --force`)."
            )

    # -- reads ----------------------------------------------------------

    def count(self) -> int:
        """Return the exact number of points in the collection."""
        return self._client.count(collection_name=self.collection, exact=True).count

    def scroll_all_payloads(self) -> list[dict[str, Any]]:
        """Return the payload of every point, paging through the collection."""
        payloads: list[dict[str, Any]] = []
        offset: Any = None
        while len(payloads) < _SCROLL_MAX_POINTS:
            records, offset = self._client.scroll(
                collection_name=self.collection,
                limit=_SCROLL_PAGE_SIZE,
                with_payload=True,
                with_vectors=False,
                offset=offset,
            )
            payloads.extend(record.payload or {} for record in records)
            if offset is None or not records:
                break
        return payloads[:_SCROLL_MAX_POINTS]

    # -- writes ---------------------------------------------------------

    def upsert_points(
        self, points: Sequence[KnowledgePoint], *, batch_size: int = 64
    ) -> int:
        """Upsert ``points`` in batches and return how many were sent."""
        if batch_size < 1:
            raise ValueError(f"batch_size must be >= 1, got {batch_size}")

        total = 0
        for start in range(0, len(points), batch_size):
            batch = points[start : start + batch_size]
            self._client.upsert(
                collection_name=self.collection,
                points=[
                    models.PointStruct(
                        id=point.qdrant_id,
                        vector=point.vector,
                        payload=point.payload,
                    )
                    for point in batch
                ],
            )
            total += len(batch)
        return total

    def delete_all(self) -> None:
        """Remove every point, falling back to a collection rebuild if needed."""
        try:
            self._client.delete(
                collection_name=self.collection,
                points_selector=models.FilterSelector(filter=models.Filter()),
            )
        except Exception as exc:  # noqa: BLE001 - rebuilt below instead
            self._recreate_empty(str(exc))
            return

        if self.count() != 0:
            self._recreate_empty("filter delete left points behind")

    def _recreate_empty(self, reason: str) -> None:
        """Delete and recreate the collection, keeping its vector size."""
        info = self._get_collection_info()
        if info is None:
            return
        dimension = info.config.params.vectors.size
        logger.warning(
            "Rebuilding knowledge collection %s after delete failed (%s)",
            self.collection,
            reason,
        )
        self._recreate_collection(dimension)

    def close(self) -> None:
        """Close the underlying client and release the storage folder."""
        self._client.close()


def open_store(
    *,
    mode: str | None = None,
    path: Path | None = None,
    url: str | None = None,
    collection: str | None = None,
) -> QdrantStore:
    """Open the knowledge store configured by settings (unless overridden)."""
    resolved_mode = (mode if mode is not None else settings.RAG_QDRANT_MODE).strip().lower()
    resolved_collection = collection if collection is not None else settings.RAG_COLLECTION

    if resolved_mode == "local":
        resolved_path = Path(path) if path is not None else Path(settings.RAG_QDRANT_PATH)
        resolved_path.mkdir(parents=True, exist_ok=True)
        try:
            client = QdrantClient(path=str(resolved_path))
        except Exception as exc:
            message = str(exc).lower()
            if "already accessed" in message or "already in use" in message:
                raise VectorStoreError(
                    f"The local knowledge store folder '{resolved_path}' is already in "
                    "use by another process. Only one process may open a local Qdrant "
                    "folder: close the other process (for example a running uvicorn "
                    "with --reload), or set RAG_QDRANT_MODE=http to use a Qdrant server."
                ) from exc
            raise VectorStoreError(
                f"Could not open the local knowledge store at '{resolved_path}': {exc}"
            ) from exc
        return QdrantStore(client, resolved_collection, storage_path=resolved_path)

    if resolved_mode == "http":
        resolved_url = url if url is not None else settings.RAG_QDRANT_URL
        try:
            client = QdrantClient(url=resolved_url)
        except Exception as exc:
            raise VectorStoreError(
                f"Could not connect to the Qdrant server at '{resolved_url}': {exc}"
            ) from exc
        return QdrantStore(client, resolved_collection)

    raise ValueError(
        f"Unknown RAG_QDRANT_MODE {resolved_mode!r}; expected 'local' or 'http'"
    )
