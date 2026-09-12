"""Tests for document parsers."""

from oneshot.parsers.text import extract_text
from oneshot.parsers.document import extract
from pathlib import Path


def test_extract_text_file(tmp_path):
    """Test plain text extraction."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("FADE IN:\n\nINT. OFFICE - DAY\n\nA man sits at a desk.")
    
    result = extract_text(str(test_file))
    assert "FADE IN" in result
    assert "INT. OFFICE" in result


def test_extract_dispatches_to_text(tmp_path):
    """Test that extract() dispatches to the correct parser."""
    test_file = tmp_path / "script.txt"
    test_file.write_text("FADE IN:\n\nINT. OFFICE - DAY")
    
    result = extract(str(test_file))
    assert "FADE IN" in result


def test_extract_unsupported_format():
    """Test that unsupported formats raise ValueError."""
    import pytest
    with pytest.raises(ValueError, match="Unsupported file format"):
        extract("file.xyz")
