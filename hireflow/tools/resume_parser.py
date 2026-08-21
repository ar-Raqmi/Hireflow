from __future__ import annotations

from pathlib import Path


class ResumeParser:
    """Extracts plain text from resume files (.txt, .md, .pdf, .docx)."""

    _TEXT_EXTENSIONS = {".txt", ".md", ".text", ""}

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

    def _read_pdf(self, source: Path) -> str:
        from pypdf import PdfReader

        reader = PdfReader(str(source))
        return "\n".join(page.extract_text() or "" for page in reader.pages)

    def _read_docx(self, source: Path) -> str:
        from docx import Document

        document = Document(str(source))
        return "\n".join(paragraph.text for paragraph in document.paragraphs)
