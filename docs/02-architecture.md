# 02 — Architecture

## System overview

```
Job posting (URL or pasted text)
        │
        ▼
┌──────────────────────── pipeline (pure, CLI-testable) ───────────────────────┐
│ 1. ingest      URL → fetched text | pasted text → normalized text            │
│ 2. analyze     LLM call #1 → JobAnalysis (company, role, lang, reqs, kw)     │
│ 3. plan        LLM call #2 (profile + JobAnalysis) → TailoringPlan           │
│                  - selected bullet IDs per station (+ optional rephrasing)   │
│                  - skills ordering                                           │
│ 4. letter      LLM call #3 (profile + JobAnalysis + plan) → LetterSlots      │
│                  - hook, fit_1, fit_2, closing_variant                       │
│ 5. validate    every bullet ID ∈ profile; rephrasings length-bounded;        │
│                language matches; no new numbers/employers introduced         │
└───────────────────────────────────────────────────────────────────────────────┘
        │
        ▼
   REVIEW STEP (UI) — human edits/approves the plan and slots
        │
        ▼
   render: merge(profile, plan, slots) → data.json → typst compile → cv.pdf + letter.pdf
        │
        ▼
   CRM: application row (company, role, status, paths, posting link, notes)
```

## Components

### profile/profile.yaml (single source of truth)
JSON-Resume-inspired, extended with **bullet pools**:

```yaml
basics: { name, email, phone, location, linkedin, ... }
stations:
  - id: example-co
    employer: "Example Consulting GmbH"
    role: "Working Student Strategy"
    period: "..."
    location: "Köln, DE"
    bullets:
      - id: exco-01
        text_de: "..."
        text_en: "..."
        tags: [data, stakeholder, consulting]
      # 5–8 bullets per station; tailoring selects 2–4
education: [...]
skills:
  - { id: sk-01, label_de: ..., label_en: ..., tags: [...] }
languages: [...]
letter_fixed:
  greeting_formal_de: "Sehr geehrte(r) ..."
  closing_de: "..."
  greeting_en: "Dear ..."
  closing_en: "..."
```

### app/schemas.py (Pydantic → JSON schemas for structured outputs)
- `JobAnalysis`: company, role_title, language ("de"|"en"), contact_person?,
  top_requirements (max 5), keywords (max 15), seniority, notes
- `TailoringPlan`: per station: list of {bullet_id, rephrased_text?}; skills_order:
  list of skill IDs; headline?; flags (e.g. relocation mention)
- `LetterSlots`: hook, fit_1, fit_2, closing_variant (each length-bounded)

### templates/typst/
- `style.typ` — shared: fonts, accent color, spacing, section heading component
- `cv.typ` — reads `data.json`; fixed layout; iterates stations/bullets from data
- `letter.typ` — fixed frame (sender block, date, recipient, greeting, signature);
  body = 3–4 slots from data

Render contract: templates must compile against `profile/profile.example.yaml`-derived
example data in CI/pytest ("golden compile test"). Layout changes are template commits,
never runtime behavior.

### app/crm.py + SQLite
One table `applications`:
`id, company, role, channel, posting_url, language, status
(draft|sent|interview|offer|rejected|withdrawn), created_at, sent_at, cv_path,
letter_path, plan_json, notes`
Status changes append to a small `events` table (audit trail → pipeline view timeline).

### app/web/ (FastAPI + one HTML page)
- `POST /applications` (paste/URL) → runs pipeline → returns draft for review
- `PUT /applications/{id}/plan` → save edited plan → re-render
- `POST /applications/{id}/render` → PDFs
- `POST /applications/{id}/sent` → status transition
- `GET /` → SPA (vanilla JS, fetch-based)

## Decisions & rationale (ADR-style, short)

| # | Decision | Rationale | Alternative rejected |
|---|----------|-----------|----------------------|
| 1 | Typst over LaTeX/docx | deterministic, fast compile, JSON injection, git-friendly | python-docx (layout drift), LaTeX (toolchain weight) |
| 2 | Bullet-ID selection over free generation | fabrication structurally impossible | "rewrite my CV" prompting |
| 3 | 3 small LLM calls over 1 | schema limits, testability, cost control | monolithic prompt |
| 4 | SQLite over Notion/Airtable | local-first, zero setup, queryable | external CRM (API friction, privacy) |
| 5 | Vanilla frontend | 3 views don't justify a framework; design constraints easier to enforce | React/Tailwind |
| 6 | Structured outputs (GA) | guaranteed parse, no retry logic | prompt-and-pray JSON |

## Security & privacy
- `profile.yaml`, `crm.db`, `output/`, `.env` are gitignored — the public repo contains
  structure and example data only.
- Only data leaving the machine: profile content + posting text → Anthropic API.
