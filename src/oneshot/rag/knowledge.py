"""Knowledge corpus schema and seed-corpus loading for RAG.

The Phase 6 knowledge store is built from small, curated JSON seed files under
``src/oneshot/rag/seed/``. This module defines the one chunk shape every seed
file must produce, the stable identifiers derived from it, and the loader that
turns the seed directory into a validated, deterministic corpus.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field, computed_field, field_validator

__all__ = [
    "KnowledgeCategory",
    "KnowledgeChunk",
    "corpus_checksum",
    "load_corpus",
    "seed_dir",
    "slugify",
]

_SLUG_MAX_LENGTH = 60
_SLUG_STRIP = re.compile(r"[^a-z0-9]+")


class KnowledgeCategory(str, Enum):
    """Cinematic-knowledge buckets used to filter and prompt during retrieval."""

    SHOT_TYPE = "shot_type"
    CAMERA_TECHNIQUE = "camera_technique"
    LENS = "lens"
    MOVEMENT = "movement"
    COMPOSITION = "composition"
    CONTINUITY = "continuity"


def slugify(text: str) -> str:
    """Return a lowercase, dash-separated identifier of at most 60 characters."""
    slug = _SLUG_STRIP.sub("-", text.lower()).strip("-")
    return slug[:_SLUG_MAX_LENGTH]


class KnowledgeChunk(BaseModel):
    """One addressable unit of cinematic knowledge.

    ``chunk_id`` is derived from category and title, so the same chunk always
    maps to the same Qdrant point id across re-ingestions.
    """

    category: KnowledgeCategory
    title: str = Field(min_length=3, max_length=80)
    body: str = Field(min_length=10, max_length=600)
    tags: list[str] = Field(default_factory=list)
    attributes: dict[str, str] = Field(default_factory=dict)

    @field_validator("tags")
    @classmethod
    def _normalize_tags(cls, tags: list[str]) -> list[str]:
        """Trim, lowercase, underscore-separate, drop blanks, and dedupe in order."""
        normalized: list[str] = []
        for tag in tags:
            value = re.sub(r"\s+", "_", tag.strip().lower())
            if value and value not in normalized:
                normalized.append(value)
        return normalized

    @field_validator("attributes")
    @classmethod
    def _validate_attributes(cls, attributes: dict[str, str]) -> dict[str, str]:
        """Reject non-string keys or values; attributes stay flat and textual."""
        for key, value in attributes.items():
            if not isinstance(key, str) or not isinstance(value, str):
                raise ValueError(  # noqa: TRY004 - invalid input is a validation error
                    "attributes must map strings to strings"
                )
        return attributes

    @computed_field  # type: ignore[prop-decorator]
    @property
    def chunk_id(self) -> str:
        """Stable identifier: ``<category>:<slugified title>``."""
        return f"{self.category.value}:{slugify(self.title)}"

    @property
    def embedding_text(self) -> str:
        """Text sent to the embedding model for this chunk."""
        return f"{self.category.value.replace('_', ' ')}: {self.title}. {self.body}"


def seed_dir() -> Path:
    """Return the directory holding the bundled knowledge seed files."""
    return Path(__file__).resolve().parent / "seed"


def load_corpus(directory: Path | None = None) -> list[KnowledgeChunk]:
    """Load every ``*.json`` seed file under ``directory`` into sorted chunks.

    Each file is ``{"category": "<category value>", "chunks": [...]}``; the file
    category is injected into all of its chunks. Duplicate ``chunk_id`` values
    across the corpus are rejected so every chunk owns exactly one vector.
    """
    root = Path(directory) if directory is not None else seed_dir()
    files = sorted(root.glob("*.json")) if root.is_dir() else []
    if not files:
        raise ValueError(f"No knowledge corpus files found in '{root}'")

    chunks: list[KnowledgeChunk] = []
    seen: dict[str, Path] = {}

    for path in files:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(  # noqa: TRY004 - malformed corpus is a data error
                f"Knowledge corpus file '{path}' must contain a JSON object"
            )

        raw_category = data.get("category")
        try:
            category = KnowledgeCategory(raw_category)
        except ValueError as exc:
            raise ValueError(
                f"Invalid category {raw_category!r} in knowledge corpus file '{path}'"
            ) from exc

        raw_chunks = data.get("chunks")
        if not isinstance(raw_chunks, list):
            raise ValueError(  # noqa: TRY004 - malformed corpus is a data error
                f"Knowledge corpus file '{path}' must contain a list of chunks"
            )

        for raw_chunk in raw_chunks:
            chunk = KnowledgeChunk(category=category, **raw_chunk)
            previous = seen.get(chunk.chunk_id)
            if previous is not None:
                raise ValueError(
                    f"Duplicate knowledge chunk id {chunk.chunk_id!r} in "
                    f"'{previous}' and '{path}'"
                )
            seen[chunk.chunk_id] = path
            chunks.append(chunk)

    return sorted(chunks, key=lambda chunk: chunk.chunk_id)


def corpus_checksum(chunks: Iterable[KnowledgeChunk]) -> str:
    """Return a stable sha256 over the canonical JSON form of ``chunks``."""
    ordered = sorted(chunks, key=lambda chunk: chunk.chunk_id)
    payload = json.dumps(
        [chunk.model_dump(mode="json") for chunk in ordered],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
