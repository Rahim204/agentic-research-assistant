"""PDF exporter using WeasyPrint (renders Markdown → HTML → PDF)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import markdown as md_lib

logger = logging.getLogger(__name__)

_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Merriweather:ital,wght@0,400;0,700;1,400&family=Source+Sans+3:wght@400;600&display=swap');

* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: 'Merriweather', Georgia, serif; font-size: 11pt; line-height: 1.7;
       color: #1a1a1a; max-width: 750px; margin: 0 auto; padding: 50px 40px; }
h1 { font-size: 22pt; border-bottom: 2px solid #2c3e50; padding-bottom: 8px; margin-bottom: 20px; }
h2 { font-size: 16pt; color: #2c3e50; margin-top: 32px; margin-bottom: 12px; border-bottom: 1px solid #bdc3c7; padding-bottom: 4px; }
h3 { font-size: 13pt; color: #34495e; margin-top: 20px; margin-bottom: 8px; }
p  { margin-bottom: 12px; text-align: justify; }
ul, ol { margin: 8px 0 12px 24px; }
li { margin-bottom: 4px; }
table { width: 100%; border-collapse: collapse; margin: 16px 0; font-size: 9pt; }
th { background: #2c3e50; color: white; padding: 8px 6px; text-align: left; }
td { padding: 6px; border-bottom: 1px solid #ecf0f1; }
tr:nth-child(even) td { background: #f8f9fa; }
blockquote { border-left: 4px solid #e74c3c; padding: 8px 16px; background: #fdf2f2;
             margin: 12px 0; color: #666; font-style: italic; }
code { background: #f4f4f4; padding: 1px 5px; border-radius: 3px; font-family: monospace; }
hr { border: none; border-top: 1px solid #ecf0f1; margin: 24px 0; }
.title-page { text-align: center; padding: 80px 0 60px; border-bottom: 2px solid #2c3e50; margin-bottom: 40px; }
.title-page h1 { border: none; font-size: 26pt; }
.title-page .meta { color: #7f8c8d; font-size: 10pt; margin-top: 16px; }
.disclaimer { background: #fff3cd; border: 1px solid #ffc107; padding: 12px 16px;
              border-radius: 4px; font-size: 9pt; margin-bottom: 20px; }
@page { size: A4; margin: 2.5cm; @bottom-center { content: counter(page); font-size: 9pt; } }
"""


def build_pdf(
    query: str,
    report_text: str,
    gaps: list[dict],
    papers: list[dict],
    citation_style: str = "apa",
) -> bytes:
    """
    Render a PDF from the report markdown and return the raw bytes.
    Requires WeasyPrint to be installed with system dependencies.
    """
    try:
        from weasyprint import HTML, CSS  # type: ignore[import]
    except ImportError as exc:
        raise RuntimeError(
            "WeasyPrint is not installed or missing system libraries. "
            "Install with: pip install weasyprint"
        ) from exc

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # Convert markdown to HTML
    html_body = md_lib.markdown(
        report_text,
        extensions=["tables", "fenced_code", "toc", "nl2br"],
    )

    # Compose full HTML
    html = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><title>Literature Review</title></head>
<body>
  <div class="title-page">
    <h1>Literature Review Report</h1>
    <div class="meta">
      <strong>Query:</strong> {_esc(query)}<br>
      <strong>Generated:</strong> {now}
    </div>
  </div>
  <div class="disclaimer">
    ⚠️ <strong>AI-Generated Content Disclaimer:</strong>
    This report was produced by an automated AI research assistant.
    All claims, citations, and summaries should be verified by a qualified researcher
    before use in academic or professional work.
  </div>
  {html_body}
</body>
</html>"""

    css = CSS(string=_CSS)
    pdf_bytes = HTML(string=html).write_pdf(stylesheets=[css])
    return pdf_bytes


def _esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
