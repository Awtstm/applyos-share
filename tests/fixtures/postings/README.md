# Posting-Fixtures

- `example-posting.html` — committete Dummy-Ausschreibung für die Offline-Tests
  (Ingest-Extraktion) und als Smoke-Input für die Live-Pipeline.
- **Echte Postings (Roadmap 2.3): lege hier 2 deutsche + 2 englische
  Ausschreibungen als `*.txt` (oder gespeicherte `*.html`) ab.** Reale Postings
  sind potenziell urheberrechtlich geschützt und bleiben lokal — sie sind über
  das Muster unten gitignored.

Die Live-Tests (`uv run pytest -m llm`) laufen automatisch über alle
`*.txt`/`*.html`-Dateien in diesem Verzeichnis.
