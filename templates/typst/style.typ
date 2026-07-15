// style.typ - shared design tokens for all ApplyOS templates.
// Source of truth: docs/04-design-system.md. One accent, neutrals do the rest.
// Fonts are vendored in assets/fonts/ and resolved via --font-path
// with --ignore-system-fonts (see Makefile) - never from the system.

// ── color ────────────────────────────────────────────────────────────
#let accent = rgb("#B45309") // the one accent (name rule, section underline)
#let ink = rgb("#1B2432") // primary text
#let ink-2 = rgb("#5B6472") // secondary text (dates, locations)
#let line-c = rgb("#E3E6EB") // neutral hairlines

// ── typography ───────────────────────────────────────────────────────
#let font-body = "Inter"
#let size-body = 10.5pt // per design system: CV body
#let size-small = 9pt // meta lines (dates, contact)
#let size-section = 11pt // section headings
#let size-name = 20pt // document header / name

// ── spacing scale (mirrors CSS --s1..--s5) ───────────────────────────
#let s1 = 4pt
#let s2 = 8pt
#let s3 = 16pt
#let s4 = 24pt
#let s5 = 40pt

// ── base document setup ──────────────────────────────────────────────
// Usage: #show: base.with(lang: "de")
#let base(lang: "de", doc) = {
  set page(paper: "a4", margin: (x: 2.2cm, y: 2cm))
  set text(font: font-body, size: size-body, fill: ink, lang: lang)
  set par(leading: 0.65em, justify: false)
  doc
}

// ── components ───────────────────────────────────────────────────────

// Section heading: uppercase, semibold, accent underline. Accent whitelist
// in the design system allows exactly this and the name rule - nothing else.
#let section-heading(title, size: size-section, space-before: s4) = {
  v(space-before, weak: true)
  text(size: size, weight: "semibold", tracking: 0.05em, upper(title))
  v(s1, weak: true)
  line(length: 100%, stroke: 0.75pt + accent)
  v(s2, weak: true)
}

// Meta line: secondary-color small text (periods, locations, contact rows).
#let meta(content, size: size-small) = text(size: size, fill: ink-2, content)
