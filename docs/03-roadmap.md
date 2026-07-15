# 03 — Roadmap

Work strictly in phase order. Each phase ends with working, tested software.
Checkboxes = GitHub issues (one issue per checkbox, milestone per phase).

## Phase 0 — Foundation (repo hygiene)
- [x] 0.1 Python project scaffold: `pyproject.toml`, ruff, pytest, `.env.example`
- [x] 0.2 Install & pin Typst CLI; `make render-example` target proves toolchain works
- [x] 0.3 CI (GitHub Actions): lint + pytest + golden compile test on push

**Done when:** `pytest` green, example Typst doc compiles in CI.

## Phase 1 — Profile & templates (the data/layout foundation)
- [x] 1.1 Define `profile.example.yaml` schema (stations, bullet pools with IDs/tags DE+EN, skills, letter_fixed)
- [x] 1.2 Fill real `profile.yaml` from existing CV + past cover letters (manual, quality gate: 5–8 bullets/station, each with DE and EN variant, tagged)
- [x] 1.3 `templates/typst/style.typ`: accent variable, typography, spacing tokens
- [x] 1.4 `cv.typ`: fixed layout, renders entirely from data.json, ATS-clean single column
- [x] 1.5 `letter.typ`: DIN-5008-ish frame (DE) + EN variant, body from slots
- [x] 1.6 Golden tests: both templates compile against example data; visual check by hand

**Done when:** `typst compile` produces a CV and letter you would actually send, from YAML alone, with zero LLM involvement.

## Phase 2 — Tailoring pipeline (CLI, no UI)
- [x] 2.1 `schemas.py`: JobAnalysis, TailoringPlan, LetterSlots (Pydantic v2, flat)
- [x] 2.2 Ingest: URL fetch + readability extraction, paste fallback
- [x] 2.3 LLM call 1 (analyze) with structured outputs; fixtures: 2 DE + 2 EN real postings
- [x] 2.4 LLM call 2 (plan): bullet-ID selection + bounded rephrasing; prompt in `app/prompts/plan.md`
- [x] 2.5 LLM call 3 (letter slots); register rules DE (Sie, formal) / EN
- [x] 2.6 Validator: IDs exist, no new numbers/employers, language match, length bounds
- [x] 2.7 CLI: `applyos tailor <url|file> --lang auto` → prints plan → `--render` → PDFs in `output/<company>-<role>/`
- [x] 2.8 Snapshot tests of plans against fixtures

**Done when:** one command turns a pasted posting into two reviewed-quality PDFs.

## Phase 3 — CRM
- [x] 3.1 SQLite schema (applications + events), migrations-lite (CREATE IF NOT EXISTS + version pragma)
- [x] 3.2 CRUD layer + status transitions (draft→sent→interview→offer/rejected/withdrawn)
- [x] 3.3 CLI: `applyos list`, `applyos sent <id>`, `applyos note <id> "..."`
- [x] 3.4 Every rendered application auto-creates a draft row (plan_json persisted for reproducibility)

**Done when:** full application history queryable; re-render any past application from its stored plan.

## Phase 4 — Web UI
- [x] 4.1 FastAPI routes wrapping pipeline + CRM (thin layer, no logic in routes)
- [x] 4.2 Design tokens in CSS (`--accent`, neutrals, spacing) per docs/04-design-system.md
- [x] 4.3 View "New Application": paste field → analysis summary → editable plan (bullet checkboxes, editable letter slots) → render → PDF preview → "Mark as sent"
- [x] 4.4 View "Pipeline": table grouped by status, inline status change, notes
- [x] 4.5 View "Profile": YAML editor with schema validation feedback
- [x] 4.6 Keyboard-first polish: paste-and-Enter starts analysis; no dead clicks

**Done when:** complete flow (paste → sent) without touching the terminal; UI passes the design rules (one accent, no gradients, no framework).

## Phase 5 — Quality of life (optional, post-MVP)
- [ ] 5.1 Follow-up reminders (sent + 14d without response → flag in Pipeline)
- [ ] 5.2 Per-application export bundle (PDFs + posting snapshot) for interview prep
- [ ] 5.3 Stats view: applications/week, response rate by channel
- [ ] 5.4 Multi-template support (consulting vs. tech CV variant)

## Explicit non-goals
- No auto-submission to job portals
- No scraping behind logins (LinkedIn etc.) — paste text instead
- No cloud deployment, no multi-user
