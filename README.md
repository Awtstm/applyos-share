# ApplyOS

Dein persönlicher Bewerbungs-Assistent, lokal auf deinem Rechner: Stellenanzeige
einfügen → maßgeschneiderter Lebenslauf + Anschreiben als PDF → alle Bewerbungen
im eingebauten Mini-CRM verfolgen.

**Das Kernversprechen:** Die KI wählt ausschließlich aus *deinem* geprüften
Profil aus und formuliert höchstens behutsam um — sie erfindet keine Fakten,
keine Zahlen, keine Erfahrungen. Ein Validator erzwingt das technisch, und vor
jedem PDF steht dein Review.

## Wichtig zu wissen, bevor du startest

- **Alles läuft lokal.** Der Server bindet nur an `127.0.0.1` — nichts ist aus
  dem Netzwerk erreichbar, es gibt keine Accounts und kein Hosting. Deine
  Daten (Profil, Bewerbungen, PDFs, Datenbank) bleiben auf deinem Rechner und
  landen nie in einem Git-Repo.
- **Einzige Ausnahme:** Für die KI-Schritte gehen Profil-Inhalte und der
  Anzeigentext an die Anthropic-API — mit **deinem eigenen API-Key** auf
  **deine eigene Rechnung**.
- **Kosten:** ca. **10–20 Cent pro Bewerbung** (Stand: Sonnet-5-Preise).
  Leg in der Anthropic-Console ein Spend-Limit fest (z. B. 5 €/Monat), dann
  kann nichts anbrennen.

## Voraussetzungen (macOS)

Du brauchst drei Werkzeuge. Öffne die Terminal-App und führe aus:

```bash
# 1. Homebrew (Paketmanager) — falls noch nicht vorhanden
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# 2. uv (Python-Verwaltung) und typst (PDF-Renderer)
brew install uv typst
```

## Installation

```bash
# Repo holen (Zugang bekommst du von dem, der es dir geschickt hat)
git clone <repo-url> applyos
cd applyos

# Geführtes Setup: prüft Werkzeuge, installiert Abhängigkeiten, legt .env an
./scripts/setup.sh
```

Das Setup-Script sagt dir am Ende genau, was noch fehlt. Die zwei manuellen
Schritte sind:

### 1. Eigenen Anthropic-API-Key anlegen

1. Konto erstellen auf [console.anthropic.com](https://console.anthropic.com).
2. Unter **Plans & Billing**: Guthaben aufladen (5–10 € reichen lange) und
   ein **Spend-Limit** setzen.
3. Unter **API Keys**: neuen Key erstellen und kopieren.
4. In der Datei `.env` (vom Setup-Script angelegt) den Platzhalter ersetzen:

   ```
   ANTHROPIC_API_KEY=sk-ant-…dein-key…
   ```

   Die `.env` ist gitignored — der Key bleibt bei dir.

### 2. Dein Profil erstellen

Dein Profil ist der Faktenpool für alle Bewerbungen — einmal sorgfältig
erstellt, immer wieder genutzt. Folge der Anleitung in
**[docs/PROFIL_ERSTELLEN.md](docs/PROFIL_ERSTELLEN.md)**: Sie enthält einen
Copy-Paste-Prompt für [claude.ai](https://claude.ai), der dich per Interview
durch deinen Lebenslauf führt und am Ende eine fertige, schema-konforme
`profile/profile.yaml` ausgibt.

## Loslegen

```bash
uv run applyos serve
```

Dann im Browser [http://127.0.0.1:8000](http://127.0.0.1:8000) öffnen:

1. **Neue Bewerbung:** Stellenanzeige einfügen (oder URL) → die Pipeline
   analysiert, bewertet die Passung (Match-Score mit ehrlichen Stärken und
   Lücken) und erstellt einen Vorschlag.
2. **Review:** Bullets an-/abwählen und umformulieren, Anschreiben-Absätze
   bearbeiten oder per Anweisung überarbeiten lassen. Gerendert wird erst,
   wenn die Validierung grün ist.
3. **PDFs** ansehen (Klick = große Ansicht), als versendet markieren.
4. **Pipeline:** Alle Bewerbungen mit Status, Notizen, Historie.

Alles geht auch im Terminal: `uv run applyos tailor <datei|url>`,
`… render`, `… list`, `… sent <id>`, `… note <id> "…"` — siehe
`uv run applyos --help`.

## Wo deine Daten liegen

| Was | Wo | Im Git-Repo? |
|---|---|---|
| Profil | `profile/profile.yaml` | nein (gitignored) |
| API-Key | `.env` | nein (gitignored) |
| Bewerbungen (PDFs + JSON) | `output/<Firma>_<Rolle>/` | nein (gitignored) |
| CRM-Datenbank | `app/crm.db` | nein (gitignored) |

## Bei Problemen

- **Validierungsfehler beim Profil:** Fehlermeldung zurück an Claude geben
  (siehe PROFIL_ERSTELLEN.md), korrigierte YAML erneut speichern.
- **„Anthropic API (400): credit balance too low":** Guthaben in der Console
  aufladen — das ist die Original-Fehlermeldung der API.
- **typst nicht gefunden:** `brew install typst`, dann Terminal neu öffnen.
- Tests laufen mit `uv run pytest` (ohne API-Key werden die Live-Tests
  automatisch übersprungen).

## Für Neugierige: Doku

Architektur, Design-System und die Regeln für Claude-Code-Sessions liegen in
[docs/](docs/) und [CLAUDE.md](CLAUDE.md). Stack: Python 3.12 · FastAPI ·
SQLite · Pydantic v2 · Anthropic API (Structured Outputs) · Typst · Vanilla
HTML/CSS/JS.
