"""Screenplay ingestion and parsing service."""

from oneshot.parsers.document import extract


def ingest_screenplay(file_path: str) -> str:
    """Extract text from a screenplay file."""
    return extract(file_path)
