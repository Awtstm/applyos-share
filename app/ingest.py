"""Ingest: turn a posting source (URL, file, or pasted text) into clean text.

First pipeline step, no LLM involved. URL fetch + readability extraction via
trafilatura (boilerplate like nav/footer/cookie banners is stripped); pasted
or file-based text is only normalized. Scraping behind logins is a non-goal
(docs/03-roadmap.md) — LinkedIn & Co. are handled by pasting the text.
"""

import re
import sys
from pathlib import Path

import trafilatura


class IngestError(Exception):
    """Source could not be fetched or no article text could be extracted."""


def normalize_text(text: str) -> str:
    """Normalize whitespace: unify newlines, strip trailing space, collapse
    3+ blank lines to one blank line."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = "\n".join(line.rstrip() for line in text.split("\n"))
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_html(html: str, url: str | None = None) -> str:
    """Readability extraction: main text from an HTML document."""
    extracted = trafilatura.extract(html, url=url, favor_recall=True)
    if not extracted:
        raise IngestError(
            "no main text could be extracted from the HTML"
            + (f" ({url})" if url else "")
        )
    return normalize_text(extracted)


def fetch_url(url: str) -> str:
    """Fetch a posting URL and extract its main text."""
    downloaded = trafilatura.fetch_url(url)
    if downloaded is None:
        raise IngestError(f"could not fetch {url}")
    return extract_html(downloaded, url=url)


def read_source(source: str) -> str:
    """Resolve a CLI source argument to posting text.

    "-"            → read pasted text from stdin
    http(s)://…    → fetch + readability extraction
    existing file  → .html/.htm are extracted, everything else read as text
    """
    if source == "-":
        return _require_text(normalize_text(sys.stdin.read()), "stdin")
    if source.startswith(("http://", "https://")):
        return fetch_url(source)
    path = Path(source)
    if not path.exists():
        raise IngestError(f"source {source!r} is neither '-', a URL, nor an existing file")
    raw = path.read_text(encoding="utf-8")
    if path.suffix.lower() in (".html", ".htm"):
        return extract_html(raw)
    return _require_text(normalize_text(raw), source)


def _require_text(text: str, origin: str) -> str:
    if not text:
        raise IngestError(f"empty posting text from {origin}")
    return text
