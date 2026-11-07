"""Tests for the cinematic knowledge schema, seed corpus loader and checksum."""

import json
import re
from pathlib import Path

import pytest
from pydantic import ValidationError

from oneshot.rag import knowledge
from oneshot.rag.knowledge import (
    KnowledgeCategory,
    KnowledgeChunk,
    corpus_checksum,
    load_corpus,
)

CATEGORIES = {
    "shot_type",
    "camera_technique",
    "lens",
    "movement",
    "composition",
    "continuity",
}

SEED_DIR = Path(knowledge.__file__).parent / "seed"

BODY = "A close-up frames the face and hands so small emotional detail reads clearly."


def _chunk(**overrides) -> KnowledgeChunk:
    data = {
        "category": KnowledgeCategory.SHOT_TYPE,
        "title": "Close Up",
        "body": BODY,
        "tags": ["intimacy"],
        "attributes": {"energy": "low"},
    }
    data.update(overrides)
    return KnowledgeChunk(**data)


def _write_corpus(directory: Path, filename: str, category: str, chunks: list[dict]) -> None:
    payload = {"category": category, "chunks": chunks}
    (directory / filename).write_text(json.dumps(payload), encoding="utf-8")


def _entry(title: str, body: str = BODY) -> dict:
    return {"title": title, "body": body, "tags": [], "attributes": {}}


def test_knowledge_categories_match_contract():
    assert {category.value for category in KnowledgeCategory} == CATEGORIES


def test_shipped_corpus_loads_with_validated_chunks():
    assert len(list(SEED_DIR.glob("*.json"))) == 6

    chunks = load_corpus()

    assert 80 <= len(chunks) <= 150
    assert len(chunks) == len({chunk.chunk_id for chunk in chunks})
    assert {chunk.category.value for chunk in chunks} == CATEGORIES
    assert [chunk.chunk_id for chunk in chunks] == sorted(chunk.chunk_id for chunk in chunks)

    for chunk in chunks:
        assert 3 <= len(chunk.title) <= 80
        assert 10 <= len(chunk.body) <= 600
        assert chunk.chunk_id.startswith(f"{chunk.category.value}:")
        assert chunk.tags == [tag.lower() for tag in chunk.tags]
        assert all(" " not in tag for tag in chunk.tags)
        assert all(isinstance(value, str) for value in chunk.attributes.values())


def test_corpus_checksum_is_deterministic_and_order_independent():
    chunks = load_corpus()

    first = corpus_checksum(chunks)
    second = corpus_checksum(chunks)
    reversed_checksum = corpus_checksum(list(reversed(chunks)))

    assert first == second == reversed_checksum
    assert re.fullmatch(r"[0-9a-f]{64}", first)


def test_duplicate_chunk_id_across_files_is_rejected(tmp_path):
    _write_corpus(tmp_path, "a_shot_types.json", "shot_type", [_entry("Close Up")])
    _write_corpus(tmp_path, "b_more_shot_types.json", "shot_type", [_entry("Close Up")])

    with pytest.raises(ValueError) as excinfo:
        load_corpus(tmp_path)

    message = str(excinfo.value)
    assert "duplicate" in message.lower()
    assert "shot_type:close-up" in message


def test_unknown_category_is_rejected(tmp_path):
    _write_corpus(tmp_path, "lighting.json", "lighting", [_entry("Hard Key Light")])

    with pytest.raises(ValueError) as excinfo:
        load_corpus(tmp_path)

    assert "lighting" in str(excinfo.value)


def test_short_title_is_rejected():
    with pytest.raises(ValidationError):
        _chunk(title="ab")


def test_short_body_is_rejected():
    with pytest.raises(ValidationError):
        _chunk(body="too short")


def test_tags_are_normalized_and_deduped():
    chunk = _chunk(tags=["  Intimacy ", "intimacy", "Close Up"])

    assert len(chunk.tags) == 2
    assert set(chunk.tags) == {"intimacy", "close_up"}
    assert all(tag == tag.lower() for tag in chunk.tags)
    assert all(" " not in tag for tag in chunk.tags)


def test_embedding_text_and_chunk_id_shape():
    chunk = _chunk(category=KnowledgeCategory.CAMERA_TECHNIQUE, title="Dolly Zoom")

    assert chunk.chunk_id == "camera_technique:dolly-zoom"
    assert re.fullmatch(r"camera_technique:[a-z0-9]+(-[a-z0-9]+)*", chunk.chunk_id)
    assert chunk.embedding_text == f"camera technique: {chunk.title}. {chunk.body}"
    assert chunk.embedding_text.startswith("camera technique: ")
    assert chunk.embedding_text.startswith(f"camera technique: {chunk.title}")
