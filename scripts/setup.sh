#!/usr/bin/env bash
# ApplyOS Setup — prüft Voraussetzungen, installiert Abhängigkeiten, legt .env an.
# Sicher mehrfach ausführbar; ändert nichts, was schon passt.
set -euo pipefail

cd "$(dirname "$0")/.."
ok()   { printf "  ✓ %s\n" "$1"; }
todo() { printf "  ✗ %s\n" "$1"; MISSING=1; }
MISSING=0

echo "ApplyOS Setup"
echo "═════════════"

echo "1) Werkzeuge"
if command -v uv >/dev/null 2>&1; then
  ok "uv gefunden ($(uv --version))"
else
  todo "uv fehlt — installieren mit: brew install uv"
fi

if command -v typst >/dev/null 2>&1; then
  TYPST_WANT="$(cat .typst-version)"
  TYPST_HAVE="$(typst --version | awk '{print $2}')"
  if [ "$TYPST_HAVE" = "$TYPST_WANT" ]; then
    ok "typst $TYPST_HAVE gefunden"
  else
    ok "typst $TYPST_HAVE gefunden (Projekt ist mit $TYPST_WANT getestet — meist unkritisch)"
  fi
else
  todo "typst fehlt — installieren mit: brew install typst"
fi

if [ "$MISSING" = "1" ]; then
  echo
  echo "Bitte fehlende Werkzeuge installieren und das Script erneut ausführen."
  exit 1
fi

echo "2) Python-Abhängigkeiten"
uv sync -q && ok "uv sync abgeschlossen"

echo "3) Konfiguration (.env)"
if [ -f .env ]; then
  ok ".env existiert"
else
  cp .env.example .env
  ok ".env aus Vorlage angelegt"
fi
if grep -q "sk-ant-\.\.\." .env 2>/dev/null || ! grep -q "^ANTHROPIC_API_KEY=sk-ant-" .env; then
  KEY_TODO=1
else
  KEY_TODO=0
  ok "API-Key ist eingetragen"
fi

echo "4) Profil"
if [ -f profile/profile.yaml ]; then
  if uv run python -c "from app.profile import load_profile; load_profile('profile/profile.yaml')" 2>/dev/null; then
    ok "profile/profile.yaml vorhanden und valide"
    PROFILE_TODO=0
  else
    echo "  ⚠ profile/profile.yaml existiert, ist aber nicht schema-konform:"
    uv run python -c "from app.profile import load_profile; load_profile('profile/profile.yaml')" 2>&1 | tail -5 | sed 's/^/    /'
    PROFILE_TODO=1
  fi
else
  PROFILE_TODO=1
fi

echo "5) Selbsttest (ohne API-Key, Live-Tests werden übersprungen)"
if uv run pytest -q >/dev/null 2>&1; then
  ok "Testsuite grün"
else
  echo "  ⚠ Testsuite nicht grün — 'uv run pytest' zeigt Details"
fi

echo
echo "═════════════"
if [ "$KEY_TODO" = "1" ] || [ "$PROFILE_TODO" = "1" ]; then
  echo "Fast fertig — noch offen:"
  [ "$KEY_TODO" = "1" ] && cat <<'EOF'
  → API-Key: auf https://console.anthropic.com anlegen (Plans & Billing:
    Guthaben + Spend-Limit setzen; Kosten ~10–20 Cent pro Bewerbung),
    dann den Key in die Datei .env eintragen:
    ANTHROPIC_API_KEY=sk-ant-…
EOF
  [ "$PROFILE_TODO" = "1" ] && cat <<'EOF'
  → Profil: Anleitung in docs/PROFIL_ERSTELLEN.md folgen (geführtes
    Claude-Interview), Ergebnis als profile/profile.yaml speichern.
EOF
else
  echo "Alles bereit!"
fi
echo
echo "Starten mit:  uv run applyos serve   →  http://127.0.0.1:8000"
