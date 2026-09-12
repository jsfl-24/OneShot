def extract_docx(file_path: str) -> str:
    """Extract text from a DOCX file using python-docx."""
    from docx import Document

    doc = Document(file_path)
    return "\n".join([para.text for para in doc.paragraphs])
