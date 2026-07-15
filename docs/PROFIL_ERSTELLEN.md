# Profil erstellen — geführter Claude-Dialog

ApplyOS braucht genau eine Datei mit deinen echten Daten: `profile/profile.yaml`.
Sie ist der einzige Faktenpool — der LLM wählt später nur daraus aus und erfindet
nichts dazu. Deshalb lohnt sich hier Sorgfalt: **Dieses Profil ist der
Qualitätsanker für jede Bewerbung.**

Der schnellste Weg ist ein geführtes Interview mit Claude auf
[claude.ai](https://claude.ai). So geht's:

## Ablauf

1. Öffne [claude.ai](https://claude.ai) und starte eine neue Unterhaltung
   (am besten mit dem aktuellsten Modell).
2. **Lade drei Dinge hoch:**
   - deinen aktuellen Lebenslauf (PDF/DOCX),
   - 1–2 alte Anschreiben (liefern Formulierungen und Kontext),
   - die Datei `profile/profile.example.yaml` aus diesem Repo (die Schema-Referenz).
3. Kopiere einen der beiden Prompts unten (DE oder EN — je nachdem, in welcher
   Sprache du das Interview führen willst; die profile.yaml wird in beiden
   Fällen zweisprachig) und schicke ihn ab.
4. Beantworte die Interview-Fragen. Nimm dir Zeit bei den Nachfragen zu
   Ergebnissen und Zahlen — genau die machen Bullets stark.
5. Speichere die ausgegebene YAML als `profile/profile.yaml`. Am einfachsten:
   die komplette YAML in Claude kopieren, dann im Terminal (im
   ApplyOS-Ordner):

   ```bash
   pbpaste > profile/profile.yaml
   ```

6. Validiere sie:

   ```bash
   uv run python -c "from app.profile import load_profile; load_profile('profile/profile.yaml')"
   ```

   Keine Ausgabe = alles gut. Bei einer Fehlermeldung: kopiere sie zurück in
   die Claude-Unterhaltung („Der Validator meldet: …") und lass die YAML
   korrigieren, dann erneut speichern und validieren.

---

## Prompt (Deutsch)

```text
Du hilfst mir, ein strukturiertes Bewerbungsprofil als YAML-Datei zu erstellen.
Ich habe drei Dateien hochgeladen: meinen Lebenslauf, alte Anschreiben und eine
Datei profile.example.yaml — Letztere ist die verbindliche Schema-Referenz für
das Ergebnis.

Führe mit mir ein strukturiertes Interview, Station für Station:

1. Verschaffe dir zuerst aus dem Lebenslauf einen Überblick und schlage mir die
   Liste der Stationen (Berufserfahrung), Ausbildung, Skills, Sprachen und
   ehrenamtlichen Engagements vor. Ich bestätige oder korrigiere.
2. Gehe dann jede Berufsstation einzeln durch. Stelle gezielte Nachfragen:
   Was war das konkrete Ergebnis? Gibt es Zahlen (Budget, Umsatzvolumen,
   Teamgröße, Zeitersparnis, Anzahl Projekte/Kunden)? Was war mein eigener
   Anteil im Unterschied zum Team? Frage nach, bis ein Bullet konkret ist —
   aber akzeptiere auch „weiß ich nicht mehr" und formuliere dann ohne Zahl.
3. Erstelle pro großer Station 5–8 Bullets (kleine Stationen dürfen weniger
   haben). Jeder Bullet: stabile ID (z. B. acme-01), deutsche UND englische
   Variante (text_de/text_en, beide idiomatisch, keine wörtliche Übersetzung),
   passende Tags (z. B. data, stakeholder, consulting, process-design).
   Markiere pro Station die 1–3 stärksten Bullets mit default: true.

Harte Ehrlichkeitsregeln — sie sind wichtiger als beeindruckende Bullets:
- Ausschließlich Fakten, die ich genannt oder ausdrücklich bestätigt habe.
- Keine Erfindungen, keine Ausschmückungen, keine "üblichen" Aufgaben ergänzen,
  die ich nicht erwähnt habe.
- Zahlen nur, wenn ich sie nenne. Niemals schätzen oder aufrunden.
- Bei Unsicherem: weglassen oder ausdrücklich vorsichtig formulieren
  (z. B. "mitgewirkt an" statt "verantwortet") — und mich fragen, was stimmt.

Am Ende:
- Gib eine VOLLSTÄNDIGE profile.yaml aus, die exakt dem Schema von
  profile.example.yaml folgt (gleiche Feldnamen und Struktur: basics,
  headline_pool, stations, education, extracurricular, skills, languages,
  letter_fixed — inklusive der festen Anschreiben-Bausteine in letter_fixed,
  die du mit mir zusammen formulierst).
- Alle IDs müssen eindeutig sein.
- Frage mich vor der finalen Ausgabe, ob offene Punkte fehlen.

Beginne mit Schritt 1.
```

---

## Prompt (English)

```text
You are helping me build a structured application profile as a YAML file.
I have uploaded three files: my CV, one or two past cover letters, and a file
called profile.example.yaml — the latter is the binding schema reference for
the result.

Run a structured interview with me, station by station:

1. First, review my CV and propose the list of work stations, education,
   skills, languages and extracurricular activities. I confirm or correct.
2. Then go through each work station one by one. Ask targeted follow-ups:
   What was the concrete outcome? Are there numbers (budget, revenue volume,
   team size, time saved, number of projects/clients)? What was my own
   contribution as opposed to the team's? Keep probing until a bullet is
   concrete — but accept "I don't remember" and phrase without a number then.
3. Produce 5–8 bullets per major station (minor stations may have fewer).
   Each bullet: a stable ID (e.g. acme-01), a German AND an English variant
   (text_de/text_en, both idiomatic, not literal translations), fitting tags
   (e.g. data, stakeholder, consulting, process-design). Mark the 1–3
   strongest bullets per station with default: true.

Hard honesty rules — they matter more than impressive bullets:
- Only facts I stated or explicitly confirmed.
- No inventions, no embellishment, no adding "typical" responsibilities I
  did not mention.
- Numbers only if I provide them. Never estimate or round up.
- When something is uncertain: leave it out or phrase it explicitly
  cautiously (e.g. "contributed to" instead of "owned") — and ask me what
  is accurate.

At the end:
- Output a COMPLETE profile.yaml that follows the schema of
  profile.example.yaml exactly (same field names and structure: basics,
  headline_pool, stations, education, extracurricular, skills, languages,
  letter_fixed — including the fixed letter fragments in letter_fixed,
  which you draft together with me).
- All IDs must be unique.
- Before the final output, ask me whether anything is missing.

Start with step 1.
```

---

## Danach

- `profile/profile.yaml` ist gitignored — sie bleibt auf deinem Rechner.
- Du kannst das Profil jederzeit im Web-UI unter **Profil** bearbeiten
  (validiert beim Speichern) oder die Datei direkt editieren.
- Faustregel für gute Bullets: konkretes Ergebnis + eigene Rolle + Zahl,
  wo es ehrlich möglich ist.
