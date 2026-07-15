// letter.typ - cover letter, DIN-5008-oriented frame (DE) with EN variant.
// Structure follows references/Anschreiben_Beispiel.docx, a local
// style reference (gitignored, not in the repo) - user-approved:
// fixed frame (letterhead, recipient, city/date, subject, greeting,
// closing formula, signature) - variable body from slots: hook,
// 2-3 fit paragraphs, closing. Target length: ~3/4 page.
//
// Data contract: see app/render_data.py letter_data(). The template
// renders slots verbatim; it never invents content.

#import "style.typ": accent, base, meta, s1, s2, s3, s4, size-name

#let data = json(bytes(sys.inputs.data))

#assert(
  data.fits.len() >= 2 and data.fits.len() <= 3,
  message: "letter body requires 2-3 fit paragraphs, got " + str(data.fits.len()),
)

#show: base.with(lang: data.lang)
// justified body; hyphenate: auto activates under justify. Paragraph
// spacing 1.5em: body paragraphs stand free with a small, scannable gap
// (clearly above the 0.7em leading) while the letter stays on one page.
#set par(leading: 0.7em, justify: true, spacing: 1.5em)

// ── letterhead (consistent with the CV header: same name size, no
// location line — the residence note lives in the closing paragraph) ──
#align(center)[
  #text(size: size-name, weight: "bold", data.sender.name)
  #v(s1, weak: true)
  #meta(data.sender.contact)
]
#v(s2, weak: true)
#line(length: 100%, stroke: 1pt + accent)
#v(s4)

// ── recipient block + city/date ──────────────────────────────────────
#stack(spacing: 0.4em, ..data.recipient.map(l => [#l]))
#v(s3)
#align(right)[#data.city, #data.date]
#v(s3)

// ── subject + greeting ───────────────────────────────────────────────
#text(weight: "semibold", data.subject)
#v(s3, weak: true)
#data.greeting

// ── body: variable slots (gaps via par spacing above) ────────────────
#data.hook

#for fit in data.fits {
  parbreak()
  fit
}
#parbreak()
#data.closing
#v(s3)

// ── closing formula + signature ──────────────────────────────────────
#data.closing_formula
#v(s4, weak: true)
#data.signature_name
