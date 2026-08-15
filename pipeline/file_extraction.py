"""
Extracts plain text from uploaded files so they can be fed into the
existing pipeline exactly like our hardcoded SAMPLE_DOCS strings were.

WHY THIS IS A SEPARATE, SMALL MODULE:
As discussed earlier - the core pipeline (extraction/classification/
summarization) only ever needs a plain text string. This module's only
job is turning a file on disk into that string. Nothing about the
pipeline, judge, or analyzer needs to know or care whether the text
originally came from a hardcoded sample, a .txt, a .pdf, or a .docx.
"""

import os


class UnsupportedFileType(Exception):
    pass


def extract_text_from_file(file_path: str) -> str:
    """Reads a file from disk and returns its plain text content."""
    ext = os.path.splitext(file_path)[1].lower()

    if ext == ".txt":
        return _extract_txt(file_path)
    elif ext == ".pdf":
        return _extract_pdf(file_path)
    elif ext == ".docx":
        return _extract_docx(file_path)
    else:
        raise UnsupportedFileType(f"Unsupported file type: {ext}. Supported: .txt, .pdf, .docx")


def _extract_txt(file_path: str) -> str:
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def _extract_pdf(file_path: str) -> str:
    from pypdf import PdfReader
    reader = PdfReader(file_path)
    pages_text = []
    for page in reader.pages:
        text = page.extract_text() or ""
        pages_text.append(text)
    full_text = "\n".join(pages_text).strip()
    if not full_text:
        raise ValueError(
            "No extractable text found in this PDF. It may be a scanned "
            "image-based PDF, which needs OCR (not implemented in this "
            "version) rather than direct text extraction."
        )
    return full_text


def _extract_docx(file_path: str) -> str:
    from docx import Document
    doc = Document(file_path)
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    full_text = "\n".join(paragraphs).strip()
    if not full_text:
        raise ValueError("No text found in this .docx file.")
    return full_text
