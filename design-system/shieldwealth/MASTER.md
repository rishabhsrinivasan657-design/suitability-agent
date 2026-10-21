# ShieldWealth design system (master)

Product: suitability and compliance workbench for wealth advisors and compliance reviewers.
Users scan many clients, open one, verify every finding, and export a record. The UI optimises for
**trust, scan speed and auditability**, not for marketing appeal.

Sources: ui-ux-pro-max searches for "Banking/Traditional Finance" colour, the "Financial Trust"
font pairing, and the Minimalism & Swiss Style guidance. The tool's generic
`--design-system` output (a dark crypto palette and a marketing landing-page pattern) did not fit
this product and was not used.

## Style
- Light, Swiss-style layout: grey canvas (`#f6f7f9`), white cards, 1px slate borders, no shadows, 6–8px radius.
- **Light only, on purpose.** Reviews get printed and exported to PDF, and the deliverable is a light document.
- Dense but calm. Use one primary action per screen: *Download report* on the review page and *Run review* on onboarding.

## Colour tokens (`ui/components.py` → `:root`)
| Token | Value | Use |
|---|---|---|
| navy | `#1e3a8a` | primary, links, data series, focus ring |
| ink / ink-2 / muted | `#0f172a` / `#475569` / `#64748b` | text hierarchy (all ≥ 4.5:1 on white) |
| gold | `#a16207` | accent only: benchmark ticks, logo check |
| good | `#166534` on `#ecfdf3` | pass / compliant |
| bad | `#b42318` on `#fef3f2` | breach / flagged |
| warn | `#92400e` on `#fffaeb` | action required / medium |

Status is never shown by colour alone. Every badge has an icon (✓ ✕ ! –) and a word.

## Typography
- IBM Plex Sans for UI text, at a 15px base size.
- IBM Plex Mono with tabular figures for every number: KPIs, amounts, rule IDs.
- Eyebrow labels: 0.72rem uppercase with +0.05–0.09em tracking.

## Layout
- Top navigation (four pages) and a context bar showing the model, market scenario, VIX and yields, with a *Session* popover for settings.
- **Client book:** KPI strip → breaches-by-rule bars → filterable review queue (rule, status, risk and search filters; CSV export).
- **Client review**, laid out as a case file:
  - identity, status badges and a facts grid;
  - KPI strip;
  - decision panel (verdict, findings, numbered actions, guardrail corrections);
  - tabs: Rule audit, Portfolio, Rebalance plan, Fund research, Audit trail.
- Tables for verification work (rule audit, re-audit, trades) are HTML with an icon and text status in each row; long rationale sits in `<details>`.

## Implementation rules
- All text in HTML fragments goes through `ui.h()`, which escapes HTML and turns `$` into `&#36;` so amounts are never parsed as LaTeX.
- Bordered `st.container`s get a `key="card_…"` so CSS can paint them white.
- Responsive grids use `auto-fit, minmax(...)`. At 375px wide there is no page-level horizontal scroll; wide tables scroll inside their own frame.
- `prefers-reduced-motion` turns off transitions, and every interactive element has a visible `:focus-visible` ring.
