from __future__ import annotations

import io
from pathlib import Path

from hireflow.domain import WorkTypeClassifier


class ResumeParser:
    """Extracts plain text from resume files (.txt, .md, .pdf, .docx)."""

    _TEXT_EXTENSIONS = {".txt", ".md", ".text", ""}
    _SUPPORTED = {*_TEXT_EXTENSIONS, ".pdf", ".docx"}

    def read(self, path: str | Path) -> str:
        source = Path(path)
        if not source.exists():
            raise FileNotFoundError(f"Resume file not found: {source}")
        suffix = source.suffix.lower()
        if suffix == ".pdf":
            return self._read_pdf(source)
        if suffix == ".docx":
            return self._read_docx(source)
        if suffix in self._TEXT_EXTENSIONS:
            return source.read_text(encoding="utf-8", errors="replace")
        raise ValueError(f"Unsupported resume format: {suffix or 'unknown'} (.txt, .pdf, .docx)")

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

    def infer_work_type(self, text: str) -> str:
        return WorkTypeClassifier.classify(text)

    def _read_pdf(self, source: Path) -> str:
        from pypdf import PdfReader

        reader = PdfReader(str(source))
        return "\n".join(page.extract_text() or "" for page in reader.pages)

    def _read_docx(self, source: Path) -> str:
        from docx import Document

        document = Document(str(source))
        return "\n".join(paragraph.text for paragraph in document.paragraphs)

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


def _approx_pages(text: str) -> int:
    return max(1, (len(text) + 2999) // 3000)