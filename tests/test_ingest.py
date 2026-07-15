"""Ingest tests: readability extraction and source dispatch — all local,
no network access."""

from pathlib import Path

import pytest

from app.ingest import IngestError, extract_html, normalize_text, read_source

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "postings"
POSTING_HTML = FIXTURES / "example-posting.html"


def test_extract_html_keeps_body_drops_boilerplate():
    text = extract_html(POSTING_HTML.read_text(encoding="utf-8"))
    assert "Business Cases" in text
    assert "Erika Beispiel" in text
    # nav / cookie banner / footer must not survive extraction
    assert "Alle akzeptieren" not in text
    assert "Impressum" not in text
    assert "Login" not in text


def test_extract_html_fails_loudly_on_empty_page():
    with pytest.raises(IngestError):
        extract_html("<html><body></body></html>")


def test_normalize_text():
    raw = "Zeile eins  \r\nZeile zwei\r\r\n\n\n\nZeile drei\n"
    assert normalize_text(raw) == "Zeile eins\nZeile zwei\n\nZeile drei"


def test_read_source_html_file():
    text = read_source(str(POSTING_HTML))
    assert "Strategy Analyst" in text


def test_read_source_plain_text_file(tmp_path):
    posting = tmp_path / "posting.txt"
    posting.write_text("Wir suchen eine:n Analyst:in.\n\n\nJetzt bewerben!\n", encoding="utf-8")
    assert read_source(str(posting)) == "Wir suchen eine:n Analyst:in.\n\nJetzt bewerben!"


def test_read_source_stdin(monkeypatch):
    import io

    monkeypatch.setattr("sys.stdin", io.StringIO("Eingefügter Posting-Text.\n"))
    assert read_source("-") == "Eingefügter Posting-Text."


def test_read_source_rejects_missing_file():
    with pytest.raises(IngestError):
        read_source("does-not-exist.txt")


def test_read_source_rejects_empty_file(tmp_path):
    empty = tmp_path / "empty.txt"
    empty.write_text("   \n", encoding="utf-8")
    with pytest.raises(IngestError):
        read_source(str(empty))
