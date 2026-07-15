// example.typ - Phase 0/1 toolchain proof.
// Compiles a minimal document exercising what the real templates rely on:
// vendored fonts, shared style tokens, JSON data injection, basic layout.

#import "style.typ": accent, base, meta, section-heading

#let data = json(bytes(sys.inputs.at("data", default: "{\"name\": \"ApplyOS\"}")))

#show: base.with(lang: "en")

#align(center)[
  #text(size: 20pt, weight: "bold")[#data.name toolchain check]
]

#section-heading[What this proves]

If this document compiles, the Typst CLI is installed, pinned, and able to:

+ render fixed layouts from a template using the shared `style.typ` tokens,
+ resolve the vendored Inter fonts deterministically (ä ö ü ß - umlauts render),
+ read injected JSON via `sys.inputs`,
+ apply the accent color #text(fill: accent)[#h(0.2em)`#B45309`#h(0.2em)] from the design system.

#v(1em)
#meta[Rendered from data: #raw(data.name) - secondary text in ink-2.]
