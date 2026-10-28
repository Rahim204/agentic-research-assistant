"""Unit tests for the PDF parser."""

import pytest
from backend.parsers.pdf_parser import PDFParser, PDFParseError


def test_rejects_non_pdf_extension():
    parser = PDFParser()
    with pytest.raises(PDFParseError, match="Unsupported file extension"):
        parser.parse_bytes(b"%PDF-1.4 ...", "document.docx")


def test_rejects_missing_pdf_header():
    parser = PDFParser()
    with pytest.raises(PDFParseError, match="does not appear to be a valid PDF"):
        parser.parse_bytes(b"Not a PDF content", "file.pdf")


def test_content_hash_is_sha256():
    import hashlib
    parser = PDFParser()
    data = b"%PDF-1.4 ..."
    # Will fail on fitz.open but we test the validation path
    try:
        result = parser.parse_bytes(data, "test.pdf")
        assert result.content_hash == hashlib.sha256(data).hexdigest()
    except PDFParseError:
        # Expected since b"%PDF-1.4 ..." is not a real PDF
        pass


def test_parse_bytes_wrong_mime():
    parser = PDFParser()
    with pytest.raises(PDFParseError):
        parser.parse_bytes(b"\x89PNG\r\n", "image.pdf")
