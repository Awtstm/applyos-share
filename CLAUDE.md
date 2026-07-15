# CLAUDE.md — ApplyOS

Personal job application engine: tailors CV + cover letter to a pasted job posting,
renders fixed-layout PDFs, tracks applications in a local CRM.

## Non-negotiable architecture rules

1. **The LLM fills slots, never layouts.** All document layout lives in Typst templates
   (`templates/typst/`). The LLM produces JSON matching `app/schemas.py` (Pydantic).
   The LLM never writes Typst code, never touches templates, never invents CV facts.
2. **Single source of truth for the profile:** `profile/profile.yaml`. Tailoring =
   selecting + lightly rephrasing existing bullets from the profile pool. Never fabricate
   experience, numbers, or skills that are not in the profile.
3. **Human review before render/send.** Every generated application passes a review step
   in the UI (editable preview). No auto-send, ever.
4. **Local-first.** SQLite (`app/crm.db`, gitignored), no cloud services beyond the
   Anthropic API. Personal data (profile.yaml, generated PDFs, DB) is gitignored.

## Stack (decided — do not re-litigate)

- Python 3.12, FastAPI, SQLite (stdlib `sqlite3` or SQLModel), Pydantic v2
- Anthropic API with **structured outputs** (`output_config.format` with JSON schema —
  GA, no beta header needed) for all extraction/tailoring calls
- Typst CLI for PDF rendering (`typst compile`), data injected via `--input data=<json>`
  or a generated `data.json` read with `json()` in the template
- Frontend: single-page vanilla HTML/CSS/JS served by FastAPI. **No React, no Tailwind,
  no UI framework, no build step.**

## Design rules (UI)

- Minimalist. One accent color only: `--accent: #B45309` (amber-700 on navy-tinted
  neutrals — see docs/04-design-system.md). **No gradients. No shadows heavier than
  1px borders. No icon libraries.**
- System font stack. Generous whitespace. Accent color used exclusively for: primary
  button, status badges, active states, links.
- Two languages in output documents (DE/EN), auto-detected from the job posting,
  overridable in the review step.

## Working conventions

- Work in the phases defined in `docs/03-roadmap.md`. Complete a phase's acceptance
  criteria before starting the next. Ask before deviating.
- Small commits, imperative messages (`feat: …`, `fix: …`, `docs: …`).
- Secrets: `ANTHROPIC_API_KEY` from environment / `.env` (gitignored). Never hardcode.
- Tests: pytest for the tailoring pipeline (schema validity, no-fabrication checks
  against profile), golden-file tests for Typst rendering (compile must succeed).

## Repository map

- `docs/` — research, architecture, roadmap, design system (read before coding)
- `profile/` — profile.example.yaml (committed) / profile.yaml (gitignored, real data)
- `templates/typst/` — cv.typ, letter.typ + shared styles
- `app/` — FastAPI app, pipeline, schemas, CRM
- `output/` — generated PDFs per application (gitignored)
