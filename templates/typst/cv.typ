// cv.typ - fixed CV layout, rendered entirely from injected data.json.
// Structure (user-approved): single column, no photo, header with name /
// headline / contact + accent rule, then experience → education →
// extracurricular (if any) → skills → languages. ATS-clean: plain text
// flow, standard bullets, no graphics.
//
// Data contract: see app/render_data.py cv_data(). All strings arrive
// already language-resolved; only section labels are chosen here.

#import "style.typ": accent, base, ink-2, s1, s2, s3, size-body, size-name, size-section, size-small
#import "style.typ": meta as style-meta, section-heading as style-section-heading

// one-page target: the CV runs its whole type scale 2pt below the
// design-system default (body 8.5pt, meta 7.5pt, headings 9pt)
#let cv-scale = 2pt
#let meta = style-meta.with(size: size-small - cv-scale + 0.5pt)
// one-page target: tighter vertical rhythm than the design-system default
// (16pt before section headings instead of 24pt, 12pt between entries)
#let cv-entry-gap = 12pt
#let section-heading = style-section-heading.with(
  size: size-section - cv-scale,
  space-before: s3,
)

#let data = json(bytes(sys.inputs.data))

#let labels = (
  de: (
    experience: "Berufserfahrung",
    education: "Ausbildung",
    extracurricular: "Engagement",
    skills: "Kenntnisse",
    languages: "Sprachen",
  ),
  en: (
    experience: "Work Experience",
    education: "Education",
    extracurricular: "Extracurricular Activities",
    skills: "Skills",
    languages: "Languages",
  ),
).at(data.lang)

#show: base.with(lang: data.lang)
// justified with hyphenation (hyphenate: auto activates under justify)
#set text(size: size-body - cv-scale)
#set par(justify: true)
#set list(marker: text(fill: ink-2)[•], indent: 0pt, body-indent: 0.5em)

// ── header ───────────────────────────────────────────────────────────
#align(center)[
  #text(size: size-name, weight: "bold", data.name)
  #v(s1, weak: true)
  #text(fill: ink-2, data.headline)
  #v(s1, weak: true)
  #meta(data.contact.join(" · "))
]
#v(s2, weak: true)
#line(length: 100%, stroke: 1pt + accent)

// ── entry component (station / education) ───────────────────────────
#let entry(title, org, location, period, bullets) = {
  grid(
    columns: (1fr, auto),
    column-gutter: s2,
    text(weight: "semibold", title),
    align(right, meta(period)),
  )
  v(s1, weak: true)
  meta(org + " · " + location)
  if bullets.len() > 0 {
    v(s1, weak: true)
    list(spacing: 0.55em, ..bullets.map(b => [#b]))
  }
  v(cv-entry-gap, weak: true)
}

// ── sections ─────────────────────────────────────────────────────────
#section-heading(labels.experience)
#for st in data.stations {
  entry(st.role, st.employer, st.location, st.period, st.bullets)
}

#section-heading(labels.education)
#for edu in data.education {
  entry(edu.degree, edu.institution, edu.location, edu.period, edu.details)
}

#if data.extracurricular.len() > 0 {
  section-heading(labels.extracurricular)
  list(spacing: 0.55em, ..data.extracurricular.map(e => [#e]))
  v(cv-entry-gap, weak: true)
}

#section-heading(labels.skills)
#data.skills.join(" · ")

#section-heading(labels.languages)
#data.languages.join(" · ")
