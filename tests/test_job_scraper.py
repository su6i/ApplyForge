"""
test_job_scraper.py — PDF-URL scraping must extract real text, never mojibake HTML garbage.

Runnable two ways (pytest is optional in this repo):
    .venv/bin/python tests/test_job_scraper.py     # plain-python self-runner
    pytest tests/test_job_scraper.py                 # if pytest is installed
"""
from __future__ import annotations

import io
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# Allow running directly (python tests/test_job_scraper.py) from anywhere.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.pipeline.job_scraper import JobScrapeError, _scrape_with_requests


def _make_minimal_pdf(text: str) -> bytes:
    """Hand-craft a tiny, valid single-page PDF containing `text` (no network, no deps)."""
    content_stream = f"BT /F1 12 Tf 10 100 Td ({text}) Tj ET".encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /Resources << /Font << /F1 4 0 R >> >> "
        b"/MediaBox [0 0 200 200] /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        f"<< /Length {len(content_stream)} >>\nstream\n".encode("latin-1")
        + content_stream
        + b"\nendstream",
    ]
    out = io.BytesIO()
    out.write(b"%PDF-1.4\n")
    offsets = [0]
    for i, obj in enumerate(objects, start=1):
        offsets.append(out.tell())
        out.write(f"{i} 0 obj\n".encode("latin-1"))
        out.write(obj)
        out.write(b"\nendobj\n")
    xref_offset = out.tell()
    out.write(f"xref\n0 {len(objects) + 1}\n".encode("latin-1"))
    out.write(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        out.write(f"{off:010d} 00000 n \n".encode("latin-1"))
    out.write(b"trailer\n")
    out.write(f"<< /Size {len(objects) + 1} /Root 1 0 R >>\n".encode("latin-1"))
    out.write(b"startxref\n")
    out.write(f"{xref_offset}\n".encode("latin-1"))
    out.write(b"%%EOF")
    return out.getvalue()


def _fake_response(content: bytes, content_type: str) -> MagicMock:
    resp = MagicMock()
    resp.content = content
    resp.headers = {"Content-Type": content_type}
    resp.raise_for_status = MagicMock()
    resp.encoding = "utf-8"
    return resp


def test_pdf_content_type_extracts_real_text_not_mojibake():
    pdf_bytes = _make_minimal_pdf("Poste de recherche postdoctorale en IA")
    fake_resp = _fake_response(pdf_bytes, "application/pdf")
    with patch("src.pipeline.job_scraper.requests.get", return_value=fake_resp):
        posting = _scrape_with_requests("https://example.org/uploads/topic.pdf")
    assert "Poste de recherche postdoctorale en IA" in posting.body
    # Must not have run the HTML parser over binary PDF bytes.
    assert "%PDF" not in posting.body
    assert "obj" not in posting.body.lower().split()


def test_pdf_detected_by_magic_bytes_without_content_type_header():
    pdf_bytes = _make_minimal_pdf("Magic byte detection works correctly here")
    fake_resp = _fake_response(pdf_bytes, "application/octet-stream")
    with patch("src.pipeline.job_scraper.requests.get", return_value=fake_resp):
        posting = _scrape_with_requests("https://example.org/download?id=42")
    assert "Magic byte detection works correctly here" in posting.body


def test_pdf_extraction_failure_aborts_before_llm_call():
    # Corrupted/undecodable PDF bytes: extraction must raise, not silently
    # fall through to garbage HTML parsing.
    garbage = b"%PDF-1.4\nthis is not a real pdf body at all"
    fake_resp = _fake_response(garbage, "application/pdf")
    with patch("src.pipeline.job_scraper.requests.get", return_value=fake_resp):
        try:
            _scrape_with_requests("https://example.org/broken.pdf")
        except JobScrapeError as exc:
            assert "pdf" in str(exc).lower()
        else:
            raise AssertionError("expected JobScrapeError for unparseable PDF")


def _run_all() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failures = 0
    for fn in tests:
        try:
            fn()
            print(f"  PASS  {fn.__name__}")
        except Exception as exc:  # noqa: BLE001
            failures += 1
            print(f"  FAIL  {fn.__name__}: {exc}")
    print(f"\n{len(tests) - failures}/{len(tests)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(_run_all())
