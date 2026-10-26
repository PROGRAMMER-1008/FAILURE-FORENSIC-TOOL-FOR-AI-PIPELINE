"""Bounded document extraction. Called in a separate process by the API."""

import io
import zipfile


class DocumentError(ValueError):
    pass


def extract(data: bytes, content_type: str, max_chars: int = 20000) -> str:
    try:
        if content_type == "text/plain":
            text = data.decode("utf-8-sig", errors="strict")
            if "\x00" in text:
                raise DocumentError("Binary content is not text")
        elif content_type == "application/pdf":
            if not data.startswith(b"%PDF-"):
                raise DocumentError("Invalid PDF signature")
            from pypdf import PdfReader

            reader = PdfReader(io.BytesIO(data), strict=True)
            if reader.is_encrypted:
                raise DocumentError("Encrypted PDFs are unsupported")
            if len(reader.pages) > 50:
                raise DocumentError("PDF exceeds 50-page limit")
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
            if not text.strip():
                raise DocumentError("No PDF text; scanned PDFs need OCR, which is unavailable")
        elif (
            content_type
            == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ):
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                entries = archive.infolist()
                if len(entries) > 1000 or sum(e.file_size for e in entries) > 10_000_000:
                    raise DocumentError("DOCX archive expansion limit exceeded")
                if "word/document.xml" not in archive.namelist():
                    raise DocumentError("Not a DOCX document")
            from docx import Document
            from docx.table import Table
            from docx.text.paragraph import Paragraph

            document = Document(io.BytesIO(data))
            pieces = []
            for child in document.element.body:
                if child.tag.endswith("}p"):
                    pieces.append(Paragraph(child, document).text)
                elif child.tag.endswith("}tbl"):
                    pieces.extend(
                        " | ".join(cell.text for cell in row.cells)
                        for row in Table(child, document).rows
                    )
            text = "\n".join(pieces)
        else:
            raise DocumentError("Unsupported content type; use UTF-8 text, PDF or DOCX")
        if not text.strip():
            raise DocumentError("Document is empty")
        if len(text) > max_chars:
            raise DocumentError("Document exceeds character limit")
        return text
    except DocumentError:
        raise
    except Exception:
        raise DocumentError("Malformed document or invalid UTF-8 encoding") from None


def _child(connection, data, content_type, max_chars, memory_mb):
    try:
        import sys

        if sys.platform == "linux":
            import resource

            resource.setrlimit(resource.RLIMIT_AS, (memory_mb * 1024 * 1024,) * 2)
            resource.setrlimit(resource.RLIMIT_CPU, (8, 8))
        connection.send((True, extract(data, content_type, max_chars)))
    except DocumentError as exc:
        connection.send((False, str(exc)))
    except (MemoryError, OSError):
        connection.send((False, "Document parser resource limit exceeded"))
    finally:
        connection.close()


def isolated_extract(data: bytes, content_type: str, max_chars: int, memory_mb: int = 256) -> str:
    import multiprocessing

    context = multiprocessing.get_context("spawn")
    parent, child = context.Pipe(duplex=False)
    process = context.Process(target=_child, args=(child, data, content_type, max_chars, memory_mb))
    process.start()
    child.close()
    try:
        if not parent.poll(10):
            raise DocumentError("Document parser deadline exceeded")
        try:
            ok, result = parent.recv()
        except EOFError:
            raise DocumentError("Document parser stopped within resource limits") from None
        if not ok:
            raise DocumentError(result)
        return result
    finally:
        if process.is_alive():
            process.terminate()
        process.join(timeout=2)
        parent.close()
