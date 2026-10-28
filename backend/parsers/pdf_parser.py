"""PDF text extraction using PyMuPDF (fitz)."""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

ALLOWED_MIME_TYPES = {"application/pdf"}
ALLOWED_EXTENSIONS = {".pdf"}


@dataclass
class ParsedPDF:
    content_hash: str
    full_text: str
    title: str | None
    authors: list[str]
    page_count: int


class PDFParseError(ValueError):
    """Raised when a PDF cannot be parsed."""


class PDFParser:
    """Extracts text and metadata from PDF files using PyMuPDF."""

    def parse_bytes(self, pdf_bytes: bytes, filename: str = "upload.pdf") -> ParsedPDF:
        """
        Parse a PDF from raw bytes.
        Validates MIME type via magic bytes and file extension.
        Raises PDFParseError on invalid or unreadable files.
        """
        # Validate extension
        ext = Path(filename).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise PDFParseError(
                f"Unsupported file extension '{ext}'. Only .pdf files are accepted."
            )

        # Validate magic bytes (%PDF-)
        if not pdf_bytes.startswith(b"%PDF-"):
            raise PDFParseError(
                f"File '{filename}' does not appear to be a valid PDF "
                "(missing %PDF- header)."
            )

        # Compute content hash for deduplication
        content_hash = hashlib.sha256(pdf_bytes).hexdigest()

        try:
            import fitz  # PyMuPDF

            doc = fitz.open(stream=pdf_bytes, filetype="pdf")  # type: ignore[call-overload]
        except Exception as exc:
            raise PDFParseError(f"Could not open '{filename}': {exc}") from exc

        if doc.is_encrypted:
            raise PDFParseError(
                f"File '{filename}' is password-protected and cannot be read."
            )

        # Extract full text
        pages: list[str] = []
        for page in doc:
            pages.append(page.get_text())
        full_text = "\n".join(pages).strip()

        if not full_text:
            logger.warning("PDF '%s' yielded no extractable text (may be scanned image).", filename)

        # Best-effort metadata extraction
        meta = doc.metadata or {}
        raw_title = meta.get("title", "").strip() or None
        raw_author = meta.get("author", "").strip()
        authors = [a.strip() for a in raw_author.split(",")] if raw_author else []

        doc.close()

        return ParsedPDF(
            content_hash=content_hash,
            full_text=full_text,
            title=raw_title,
            authors=authors,
            page_count=doc.page_count,
        )

    def parse_file(self, path: Path) -> ParsedPDF:
        """Parse a PDF from a file path."""
        if not path.exists():
            raise PDFParseError(f"File not found: {path}")
        return self.parse_bytes(path.read_bytes(), path.name)
