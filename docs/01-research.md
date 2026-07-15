# 01 — Research Synthesis

Condensed findings across the five relevant domains. This is the evidence base for the
architecture decisions in `02-architecture.md`.

## 1. AI application building (LLM pipelines)

**Structured outputs are the backbone.** The Anthropic API supports schema-guaranteed
JSON via `output_config.format` (JSON schema, generally available; the older
`output_format` + beta header `structured-outputs-2025-11-13` still works during a
transition period). Constrained decoding guarantees *shape*, not *truth* — the model
can still produce well-formatted wrong content. Consequences for this project:

- Every LLM call in the pipeline defines a Pydantic model → JSON schema → structured output.
  No regex parsing, no retry-on-malformed-JSON logic needed.
- Schema limits exist (nesting depth, parameter counts). Keep schemas flat:
  `JobAnalysis`, `TailoringPlan`, `LetterSlots` as three separate calls rather than one
  mega-schema.
- Truthfulness is enforced *architecturally*, not by prompting alone: the tailoring call
  receives the profile bullet pool with stable IDs and must return **selected IDs +
  optional rephrasing**, so fabricated experience is structurally impossible. A
  post-validation step checks every returned ID exists in the profile.

**Pipeline pattern: extract → plan → generate → validate → render.** Multi-step with
small focused calls beats one giant prompt: cheaper, debuggable, each step independently
testable.

## 2. Software structure

- **Local-first, boring stack.** FastAPI + SQLite + vanilla frontend. No auth needed
  (localhost), no ORM ceremony required, trivial backup (copy one file).
- **Separation:** `pipeline/` (pure functions: job text in → validated JSON out),
  `render/` (JSON + template → PDF), `crm/` (persistence), `web/` (thin HTTP layer).
  The pipeline must be runnable from CLI without the web layer (Phase 2 before Phase 4).
- **Data/layout separation for documents** is a solved pattern in the Typst ecosystem:
  JSON Resume–style templates read structured data (`json()` / `yaml()` in Typst),
  layout logic lives in a base template. brilliant-cv even runs pixel-regression tests
  in CI — we adopt the lighter version: "template must compile against example data"
  as a golden test.

## 3. Career advisory (what makes tailoring actually good)

- **ATS reality:** parseable single-column layouts, standard section names, keywords
  mirrored from the posting *where truthful*. Typst produces clean text-layer PDFs;
  the template should avoid multi-column tricks for the ATS variant.
- **DACH conventions matter:** tabellarischer Lebenslauf, photo optional (increasingly
  omitted), signature + date on cover letters, formal register (Sie), company research
  in the opening paragraph. NL/international: 1-page-max pressure is weaker than in the
  US but conciseness wins; no photo; English register more direct.
- **Tailoring that works:** reorder + select bullets by relevance to the posting's top
  3–5 requirements; mirror the posting's terminology (e.g. "stakeholder management" vs
  "Schnittstellenfunktion"); one quantified proof point per claimed skill. Cover letter =
  hook (why this company, specific) → fit paragraph 1 (strongest overlap) → fit
  paragraph 2 (second overlap or trajectory) → close. Only the hook and fit paragraphs
  are LLM-variable; frame is fixed.
- **What kills applications:** generic letters, keyword stuffing, fabricated-sounding
  claims, inconsistency between CV and letter. Hence: both documents generated from the
  same `TailoringPlan` in one coherent pass.

## 4. AI implementation (operational)

- **Model choice per step:** cheap/fast model for extraction (job posting → JobAnalysis),
  stronger model for the tailoring plan and letter slots. Configurable in one place.
- **Cost envelope:** per application ≈ 3 calls, a few thousand tokens → cents. Irrelevant
  at personal scale; no caching infrastructure needed.
- **Failure modes to handle:** posting URL behind login/JS (fallback: paste text),
  posting language ≠ expected, missing company/contact info (nullable fields + UI
  prompts), model refusal/truncation (check `stop_reason`).
- **Evaluation:** keep a small fixture set of real postings (DE + EN) and snapshot the
  TailoringPlan output; review diffs when changing prompts. Prompts live in versioned
  files (`app/prompts/`), not inline strings.

## 5. UI design (minimalist, one accent)

- One accent color as a CSS variable; neutrals do all other work. Accent reserved for
  primary action, active state, status badges → instant visual hierarchy without any
  framework.
- System font stack (`-apple-system, "Segoe UI", Roboto, …`): zero load time, native
  feel, appropriate for a tool.
- Three views cover the whole workflow: **New Application** (paste → analyze → review →
  render → mark sent), **Pipeline** (table/board of applications by status), **Profile**
  (edit the YAML with validation). Density over decoration; borders (1px) over shadows;
  no gradients per project constraint.
- Status colors: use the accent for "active/attention" states only; success/failure can
  stay neutral (text labels) to preserve the one-accent rule strictly, or use
  desaturated semantic grays.

## Key external references

- Anthropic structured outputs docs: platform.claude.com/docs/en/build-with-claude/structured-outputs
- Typst Universe CV ecosystem (data/layout separation patterns): basic-resume,
  brilliant-cv, jsume, typst-jsonresume-cv
- JSON Resume schema (inspiration for profile.yaml shape — we extend it with
  bullet pools + tags)
