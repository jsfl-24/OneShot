from pathlib import Path


def extract(file_path: str) -> str:
    """Dispatch to the correct parser based on file extension."""
    ext = Path(file_path).suffix.lower()

    if ext == ".pdf":
        from oneshot.parsers.pdf import extract_pdf
        return extract_pdf(file_path)
    elif ext == ".docx":
        from oneshot.parsers.docx import extract_docx
        return extract_docx(file_path)
    elif ext == ".txt":
        from oneshot.parsers.text import extract_text
        return extract_text(file_path)
    else:
        raise ValueError(f"Unsupported file format: {ext}")
