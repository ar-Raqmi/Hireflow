from __future__ import annotations

import io
from pathlib import Path


class ResumeParser:
    """Extracts plain text from resume files (.txt, .md, .pdf, .docx)."""

    _TEXT_EXTENSIONS = {".txt", ".md", ".text", ""}
    _SUPPORTED = {*_TEXT_EXTENSIONS, ".pdf", ".docx"}

    def parse_bytes(self, filename: str, content: bytes) -> tuple[str, int]:
        suffix = Path(filename).suffix.lower()
        if suffix not in self._SUPPORTED:
            raise ValueError(
                f"Unsupported resume format: {suffix or 'unknown'} (.txt, .pdf, .docx)"
            )
        if suffix == ".pdf":
            return self._parse_pdf_bytes(content)
        if suffix == ".docx":
            return self._parse_docx_bytes(content)
        text = content.decode("utf-8", errors="replace")
        return text, _approx_pages(text)

    def validate(self, filename: str | None) -> None:
        if filename is None:
            raise ValueError("No file provided")
        suffix = Path(filename).suffix.lower()
        if suffix not in self._SUPPORTED:
            raise ValueError(
                f"Unsupported resume format: {suffix or 'unknown'} (.txt, .pdf, .docx)"
            )

    def _parse_pdf_bytes(self, content: bytes) -> tuple[str, int]:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(content))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        return text, len(reader.pages)

    def _parse_docx_bytes(self, content: bytes) -> tuple[str, int]:
        from docx import Document

        document = Document(io.BytesIO(content))
        text = "\n".join(paragraph.text for paragraph in document.paragraphs)
        return text, _approx_pages(text)

    def pdf_page_images(self, content: bytes, max_pages: int = 6) -> list[bytes]:
        import fitz

        pages: list[bytes] = []
        document = fitz.open(stream=content, filetype="pdf")
        for index, page in enumerate(document):
            if index >= max_pages:
                break
            pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2))
            pages.append(pixmap.tobytes("png"))
        return pages


def _approx_pages(text: str) -> int:
    return max(1, (len(text) + 2999) // 3000)
