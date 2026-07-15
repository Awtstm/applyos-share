# 04 — Design System

Applies to the web UI **and** the PDF templates (shared accent, shared restraint).

## Principles
1. One accent color. Everything else is neutral.
2. No gradients. No decorative shadows. Borders (1px) create structure.
3. Density over decoration — this is a tool used daily, not a landing page.
4. Typography and whitespace do the design work.

## Tokens (CSS)

```css
:root {
  /* the one accent — amber on navy-tinted neutrals */
  --accent:        #B45309;
  --accent-weak:   #FDF3E7;   /* accent background tint (badges, active rows) */

  /* neutrals (navy-tinted gray scale) */
  --ink:           #1B2432;   /* primary text */
  --ink-2:         #5B6472;   /* secondary text */
  --line:          #E3E6EB;   /* borders */
  --bg:            #FFFFFF;
  --bg-2:          #F7F8FA;   /* page background / table stripes */

  /* spacing scale */
  --s1: 4px; --s2: 8px; --s3: 16px; --s4: 24px; --s5: 40px;

  --radius: 6px;
  --font: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
          "Helvetica Neue", Arial, sans-serif;
  --mono: ui-monospace, "SF Mono", "Cascadia Code", Consolas, monospace;
}
```

## Accent usage — exhaustive whitelist
- Primary button (solid `--accent`, white text)
- Active nav item (text color + 2px bottom border)
- Status badges (`--accent-weak` bg + `--accent` text) for states needing attention
  (draft, interview); terminal states (sent, rejected) stay neutral gray
- Links and focus rings

Anything else: neutral. If in doubt, neutral.

## Components (all hand-rolled, ~150 lines CSS total)
- **Button:** primary (accent) / secondary (1px `--line` border, `--ink` text). No hover
  transforms; hover = slight darken.
- **Input/textarea:** 1px border, focus = accent border. The paste field on "New
  Application" is the hero element: large, centered, monospace.
- **Table (Pipeline):** row height 44px, `--bg-2` header, 1px row separators, status
  badge right-aligned.
- **Card (review step):** 1px border, `--radius`, `--s4` padding. Bullet checkboxes with
  editable text on click.

## PDF templates (Typst)
- Same accent (`#B45309`) for: name header rule, section heading underline — nothing else.
- CV: single column, 10.5pt body, generous section spacing, no icons, no photo by default.
- Letter: DIN-5008-oriented sender/recipient block (DE variant), justified off,
  1.15 line height.

## Anti-patterns (reject in code review)
Gradients · multiple accents · icon fonts · animation beyond 100ms opacity ·
component libraries · dark mode (later, maybe) · emoji in UI text
