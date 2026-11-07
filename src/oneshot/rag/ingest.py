"""Idempotent ingestion of the cinematic knowledge corpus into Qdrant.

Ingestion is safe to repeat: chunks map to deterministic point ids, and a
re-run is skipped when every stored point already belongs to the current
embedding signature and corpus checksum. A signature change is refused rather
than mixed into the collection, because vectors from different models are not
comparable.

Run manually with ``python -m oneshot.rag.ingest [--force]``.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from oneshot.config import settings
from oneshot.rag.embeddings import EmbeddingModelError, dimension, embed_texts, signature
from oneshot.rag.knowledge import corpus_checksum, load_corpus
from oneshot.rag.store import (
    CollectionMismatchError,
    KnowledgePoint,
    QdrantStore,
    open_store,
    point_uuid,
)

if TYPE_CHECKING:
    from oneshot.rag.knowledge import KnowledgeChunk

__all__ = ["IngestReport", "ingest_corpus", "main", "seed_knowledge_if_needed"]

logger = logging.getLogger(__name__)

_FORCE_HINT = (
    "Rebuild the knowledge collection explicitly with force=True or "
    "`python -m oneshot.rag.ingest --force`."
)


@dataclass
class IngestReport:
    """Outcome of one ingestion run."""

    signature: str
    dimension: int
    corpus_sha: str
    chunks: int
    embedded: int
    upserted: int
    skipped: int
    collection: str


def _build_point(
    chunk: KnowledgeChunk, vector: list[float], sig: str, corpus_sha: str
) -> KnowledgePoint:
    """Assemble the stored point for one chunk, with its full retrieval payload."""
    return KnowledgePoint(
        chunk_id=chunk.chunk_id,
        qdrant_id=point_uuid(chunk.chunk_id),
        vector=vector,
        payload={
            "chunk_id": chunk.chunk_id,
            "category": chunk.category.value,
            "title": chunk.title,
            "body": chunk.body,
            "tags": list(chunk.tags),
            "attributes": dict(chunk.attributes),
            "embedding_signature": sig,
            "corpus_sha": corpus_sha,
        },
    )


async def ingest_corpus(
    *, force: bool = False, store: QdrantStore | None = None
) -> IngestReport:
    """Embed and store the whole knowledge corpus, skipping work when current."""
    chunks = load_corpus()
    if not chunks:
        raise ValueError("The knowledge corpus is empty; nothing to ingest")

    corpus_sha = corpus_checksum(chunks)
    sig = signature()
    dim = dimension()

    owned = store is None
    active = store if store is not None else open_store()
    try:
        recreate = force
        payloads: list[dict[str, Any]] = []
        try:
            await asyncio.to_thread(active.ensure_collection, dim)
        except CollectionMismatchError:
            if not force:
                raise
            # The collection is rebuilt only after the replacement vectors are
            # validated, so existing data survives a failed embedding call.
        else:
            if not force:
                payloads = await asyncio.to_thread(active.scroll_all_payloads)

        if not force and payloads:
            stored_signatures = sorted(
                {str(payload.get("embedding_signature")) for payload in payloads}
            )
            stale = any(
                payload.get("embedding_signature") != sig for payload in payloads
            )
            if stale:
                raise EmbeddingModelError(
                    f"Knowledge collection {active.collection!r} holds vectors from "
                    f"embedding signature(s) {stored_signatures} but the current "
                    f"signature is {sig!r}. Vectors from different models cannot be "
                    f"mixed. {_FORCE_HINT}"
                )

        if not force and len(payloads) == len(chunks) and all(
            payload.get("embedding_signature") == sig
            and payload.get("corpus_sha") == corpus_sha
            for payload in payloads
        ):
            logger.info(
                "Knowledge corpus already ingested into %s (%d chunks, %s)",
                active.collection,
                len(chunks),
                corpus_sha[:12],
            )
            return IngestReport(
                signature=sig,
                dimension=dim,
                corpus_sha=corpus_sha,
                chunks=len(chunks),
                embedded=0,
                upserted=0,
                skipped=len(chunks),
                collection=active.collection,
            )

        vectors = await embed_texts(
            [chunk.embedding_text for chunk in chunks],
            concurrency=settings.RAG_EMBED_CONCURRENCY,
        )

        if len(vectors) != len(chunks):
            raise EmbeddingModelError(
                f"Embedding count mismatch for signature {sig!r}: expected "
                f"{len(chunks)} vectors but received {len(vectors)}."
            )
        for index, vector in enumerate(vectors):
            if len(vector) != dim:
                raise EmbeddingModelError(
                    f"Embedding dimension mismatch for signature {sig!r}: expected "
                    f"{dim} values but vector {index} has {len(vector)}. Re-ingest "
                    "with a matching embedding model before querying."
                )

        points = [
            _build_point(chunk, vector, sig, corpus_sha)
            for chunk, vector in zip(chunks, vectors, strict=True)
        ]

        # Destructive step comes last: only after every vector validated.
        if recreate:
            await asyncio.to_thread(active.ensure_collection, dim, force_recreate=True)
        else:
            await asyncio.to_thread(active.delete_all)
        upserted = await asyncio.to_thread(active.upsert_points, points)

        logger.info(
            "Ingested %d knowledge chunks into %s (embedded=%d, upserted=%d, %s)",
            len(chunks),
            active.collection,
            len(vectors),
            upserted,
            corpus_sha[:12],
        )
        return IngestReport(
            signature=sig,
            dimension=dim,
            corpus_sha=corpus_sha,
            chunks=len(chunks),
            embedded=len(vectors),
            upserted=upserted,
            skipped=0,
            collection=active.collection,
        )
    finally:
        if owned:
            active.close()


async def seed_knowledge_if_needed(*, force: bool = False) -> IngestReport | None:
    """Seed the knowledge collection on first run; return None when already full."""
    store = open_store()
    try:
        try:
            existing = await asyncio.to_thread(store.count)
        except Exception as exc:  # noqa: BLE001 - a missing collection means "empty"
            logger.debug(
                "Knowledge collection %s is not populated yet (%s); seeding",
                store.collection,
                exc,
            )
            existing = 0

        if existing > 0 and not force:
            return None

        return await ingest_corpus(force=force, store=store)
    finally:
        store.close()


def main(argv: list[str] | None = None) -> int:
    """CLI entry point: ``python -m oneshot.rag.ingest [--force]``."""
    parser = argparse.ArgumentParser(
        description="Ingest the OneShot cinematic knowledge corpus into Qdrant."
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Rebuild the collection even when it is current or was built elsewhere.",
    )
    args = parser.parse_args(argv)

    report = asyncio.run(ingest_corpus(force=args.force))
    for field in (
        "collection",
        "chunks",
        "embedded",
        "upserted",
        "skipped",
        "signature",
        "dimension",
        "corpus_sha",
    ):
        print(f"{field}={getattr(report, field)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
