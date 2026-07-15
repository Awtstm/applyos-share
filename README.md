# ApplyOS

Dein persönlicher Bewerbungs-Assistent, komplett auf deinem eigenen Mac:
Stellenanzeige einfügen → maßgeschneiderter Lebenslauf + Anschreiben als PDF →
alle Bewerbungen in einer eingebauten Übersicht verfolgen.

Die KI erfindet dabei nichts: Sie wählt nur aus deinem einmal angelegten,
geprüften Profil aus — und vor jedem PDF siehst du alles und kannst es ändern.

> **Was du brauchst**
> - einen **Mac**
> - **~30 Minuten** für die Einrichtung
> - eine **Kreditkarte** für das KI-Guthaben (~5 € reichen für Dutzende
>   Bewerbungen — du zahlst nur, was du nutzt, ca. 10–20 Cent pro Bewerbung)

**Privatsphäre:** Alles läuft nur auf deinem Rechner und ist aus dem Internet
nicht erreichbar. Es gibt keine Konten und keinen Server von uns. Einzige
Ausnahme: Für die KI-Schritte werden dein Profil und die Stellenanzeige an
Anthropic (den KI-Anbieter) geschickt — mit deinem eigenen Schlüssel, auf
deine eigene Rechnung.

---

## Schritt 0 — Das Terminal öffnen

Die Einrichtung läuft über das **Terminal** — ein Programm, in das man Befehle
als Text eintippt. Keine Sorge, du musst nichts selbst formulieren:

1. Drücke **Cmd + Leertaste**, tippe **Terminal**, drücke **Enter**.
2. Es öffnet sich ein Fenster mit einer Textzeile, die mit `%` oder `$` endet
   — dort werden Befehle eingegeben.

**Das Prinzip für alles Weitere:** Kopiere die Befehle aus dieser Anleitung
**einzeln** (jeweils den ganzen grauen Block), füge sie im Terminal mit
**Cmd + V** ein und drücke **Enter**. Warte, bis wieder die Zeile mit `%`
erscheint — dann ist der Befehl fertig und der nächste kommt dran.

---

## Schritt 1 — ApplyOS herunterladen

1. Lade das Paket herunter:
   **[applyos-share herunterladen (ZIP)](https://github.com/Awtstm/applyos-share/archive/refs/heads/main.zip)**
2. Im Ordner **Downloads** liegt danach `applyos-share-main.zip` — Doppelklick
   entpackt es zu einem Ordner **`applyos-share-main`**.
3. Ziehe diesen Ordner im Finder in deinen Ordner **Dokumente**.

**Das solltest du sehen:** In Dokumente liegt jetzt ein Ordner
`applyos-share-main` mit Unterordnern wie `app`, `docs` und `profile`.

---

## Schritt 2 — Homebrew installieren

Homebrew ist der „App Store fürs Terminal" — damit installieren wir gleich
zwei Werkzeuge. Kopiere in das Terminal:

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

- Das Terminal fragt nach deinem **Mac-Passwort** (das vom Anmelden). **Beim
  Tippen erscheint nichts — kein Punkt, kein Sternchen. Das ist normal.**
  Einfach tippen und Enter drücken.
- Zwischendurch einmal **Enter** drücken, wenn „Press RETURN…" erscheint.
- Die Installation dauert einige Minuten.

**Das solltest du sehen:** am Ende `Installation successful!` und darunter
einen Abschnitt **„Next steps"**.

Falls dort unter „Next steps" zwei Befehle mit `brew shellenv` angezeigt
werden, führe genau diese beiden aus (kopieren, einfügen, Enter) — oder nutze
diesen Block, der dasselbe tut:

```bash
echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile && eval "$(/opt/homebrew/bin/brew shellenv)"
```

Prüfen:

```bash
brew --version
```

**Das solltest du sehen:** eine Versionsnummer wie `Homebrew 6.x.x` — keine
Meldung „command not found".

---

## Schritt 3 — Die zwei Werkzeuge installieren

```bash
brew install uv typst
```

(`uv` verwaltet die Programmiersprache Python für dich, `typst` erzeugt die
PDFs. Beides läuft unsichtbar im Hintergrund.)

**Das solltest du sehen:** mehrere Zeilen Download-Fortschritt, am Ende
wieder die normale Eingabezeile — keine rote Fehlermeldung.

---

### Schritt 4: In den ApplyOS-Ordner wechseln

Das Terminal muss wissen, wo der ApplyOS-Ordner liegt. Dafür wechselst du
mit dem Befehl `cd` (kurz für „change directory") in den Ordner hinein.

Der genaue Pfad hängt davon ab, wohin du den Ordner gelegt hast — so
findest du ihn ganz ohne Tippen heraus:

1. Öffne den Ordner `applyos-share-main` **nicht**, sondern suche ihn im
   Finder, sodass du ihn als Symbol siehst (z. B. in „Dokumente").
2. Klicke den Ordner **einmal** an, damit er markiert ist.
3. Drücke **⌥ Option + ⌘ Cmd + C** — das kopiert den vollständigen
   Pfad des Ordners in die Zwischenablage.
   (Alternative: Rechtsklick auf den Ordner, dann die **Option-Taste ⌥
   gedrückt halten** — aus „… kopieren" wird „… als Pfadname kopieren".)
4. Wechsle ins Terminal und tippe `cd` gefolgt von **einem Leerzeichen**.
5. Füge den Pfad mit **⌘ Cmd + V** ein und drücke **Enter**.

Die Zeile sieht dann zum Beispiel so aus (dein Pfad kann anders lauten —
das ist in Ordnung): cd /Users/alexander/Documents/applyos-share-main

**Das solltest du sehen:** Keine Meldung — die Eingabezeile zeigt jetzt
aber den Ordnernamen `applyos-share-main` an. Das heißt: Du bist „im"
Ordner, und alle weiteren Befehle wirken dort.

**Falls „no such file or directory" erscheint:** Zwischen `cd` und dem
Pfad fehlt vermutlich das Leerzeichen, oder der Pfad wurde nicht
vollständig eingefügt. Wiederhole die Schritte 1–5.

Tipp für alle weiteren Male: Es geht auch ohne Kopieren — tippe
`cd `, ziehe den Ordner einfach mit der Maus aus dem Finder ins
Terminal-Fenster (der Pfad erscheint automatisch) und drücke Enter.
---

## Schritt 5 — Automatisches Setup laufen lassen

```bash
bash scripts/setup.sh
```

**Das solltest du sehen:** eine Checkliste mit Häkchen —

```
1) Werkzeuge
  ✓ uv gefunden (…)
  ✓ typst 0.15.0 gefunden
2) Python-Abhängigkeiten
  ✓ uv sync abgeschlossen
3) Konfiguration (.env)
  ✓ .env aus Vorlage angelegt
…
5) Selbsttest …
  ✓ Testsuite grün
```

— und am Ende zwei offene Punkte: **API-Key** und **Profil**. Die machen wir
jetzt.

---

## Schritt 6 — KI-Schlüssel anlegen (einmalig)

Der Schlüssel verbindet ApplyOS mit der KI von Anthropic — auf deine Rechnung,
mit Limit, damit nichts anbrennen kann.

1. Gehe im Browser auf **[console.anthropic.com](https://console.anthropic.com)**
   und erstelle ein Konto (E-Mail genügt).
2. Klicke links auf **Plans & Billing** → Guthaben aufladen (**5 $ reichen
   lange**) → dort auch ein **Spend-Limit** setzen (z. B. 10 $/Monat).
3. Klicke links auf **API Keys** → **Create Key** → dem Key einen beliebigen
   Namen geben → den angezeigten Schlüssel (beginnt mit `sk-ant-`) **kopieren**.
   Er wird nur einmal angezeigt.
4. Zurück im Terminal — öffne die Konfigurationsdatei (eine kleine Textdatei,
   in der dein Schlüssel gespeichert wird; sie bleibt auf deinem Rechner):

   ```bash
   open -e .env
   ```

   Es öffnet sich TextEdit. Ersetze in der ersten Zeile den Platzhalter
   hinter `ANTHROPIC_API_KEY=` durch deinen kopierten Schlüssel, sodass dort
   steht:

   ```
   ANTHROPIC_API_KEY=sk-ant-…dein-langer-schlüssel…
   ```

   Speichern mit **Cmd + S**, Fenster schließen.

---

## Schritt 7 — Dein Profil erstellen (einmalig, der wichtigste Schritt)

Dein Profil ist die Faktensammlung, aus der jede Bewerbung gebaut wird.
Du erstellst es im Gespräch mit Claude auf [claude.ai](https://claude.ai) —
die komplette Anleitung mit fertigem Gesprächs-Text steht in
**[docs/PROFIL_ERSTELLEN.md](docs/PROFIL_ERSTELLEN.md)**
(auf GitHub lesbar oder mit `open docs/PROFIL_ERSTELLEN.md` öffnen).

Kurzfassung: Lebenslauf + alte Anschreiben hochladen, Interview beantworten,
am Ende gibt Claude eine fertige Profil-Datei aus. Speichern geht am
einfachsten so: In Claude die ausgegebene Datei **komplett kopieren**, dann im
Terminal:

```bash
pbpaste > profile/profile.yaml
```
Hier erst den command ins terminal kopieren, noch NICHT Enter drücken, dann die YAML datei von claude "kopieren", dann im Terminal Enter drücken.
(Das schreibt deine Zwischenablage in die richtige Datei.) Danach prüfen:

```bash
bash scripts/setup.sh
```

**Das solltest du sehen:** `✓ profile/profile.yaml vorhanden und valide` und
`Alles bereit!`. Falls stattdessen ein Fehler kommt: die Meldung in die
Claude-Unterhaltung zurückkopieren („Der Validator meldet: …"), die
korrigierte Datei erneut kopieren und `pbpaste > profile/profile.yaml`
wiederholen.

---

## Schritt 8 — Starten

```bash
uv run applyos serve
```

**Das solltest du sehen:** `ApplyOS Web-UI: http://127.0.0.1:8000`.

Öffne im Browser: **[http://127.0.0.1:8000](http://127.0.0.1:8000)** —
Stellenanzeige einfügen, Vorschlag prüfen und anpassen, PDFs ansehen, fertig.

Das Terminal-Fenster bleibt dabei geöffnet (dort läuft das Programm).
Beenden: im Terminal **Ctrl + C** drücken.

**Ab jetzt gilt für jede Nutzung:** Terminal öffnen →
`cd ~/Documents/applyos-share-main` → `uv run applyos serve` → Browser.

---

## Wenn etwas hakt

- **„command not found: brew"** (nach Schritt 2): Die zwei „Next steps"-Befehle
  aus dem Homebrew-Abschluss fehlen noch — den `brew shellenv`-Block aus
  Schritt 2 ausführen, dann Terminal-Fenster schließen und neu öffnen.
- **„No such file or directory"** (bei Schritt 4): Der Ordner liegt woanders
  oder heißt anders. Im Finder prüfen: Liegt `applyos-share-main` wirklich
  direkt in Dokumente? Falls er z. B. noch in Downloads liegt: dorthin ziehen
  und Schritt 4 wiederholen.
- **„Address already in use"** (bei Schritt 8): ApplyOS läuft schon in einem
  anderen Terminal-Fenster oder -Tab. Entweder: das andere Fenster suchen und
  dort **Ctrl + C** drücken. Oder mit anderem „Port" starten:
  `uv run applyos serve --port 8001` — dann im Browser
  `http://127.0.0.1:8001` öffnen.
- **„Anthropic API (400): credit balance too low":** Dein KI-Guthaben ist
  leer. Auf [console.anthropic.com](https://console.anthropic.com) →
  **Plans & Billing** → Guthaben aufladen.
- **Profil-Fehlermeldung beim Validieren:** Die komplette Meldung in deine
  Claude-Unterhaltung kopieren, korrigierte Datei erneut mit
  `pbpaste > profile/profile.yaml` speichern, `bash scripts/setup.sh`
  wiederholen.
- **„typst nicht gefunden":** `brew install typst` ausführen, Terminal
  schließen und neu öffnen, weitermachen.

---

## Für Entwickler

`git clone https://github.com/Awtstm/applyos-share.git && cd applyos-share && ./scripts/setup.sh`

Stack: Python 3.12 · FastAPI · SQLite · Pydantic v2 · Anthropic API
(Structured Outputs) · Typst · Vanilla HTML/CSS/JS. Architektur,
Design-System und Roadmap in [docs/](docs/), Regeln für Claude-Code-Sessions
in [CLAUDE.md](CLAUDE.md). Tests: `uv run pytest` (Live-LLM-Tests laufen nur
mit konfiguriertem Key: `uv run pytest -m llm`). CLI statt Web-UI:
`uv run applyos --help`. Lizenz: MIT.
