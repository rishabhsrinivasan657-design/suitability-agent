"""Shared Streamlit building blocks for the ShieldWealth workbench.

Design system (see design-system/shieldwealth/MASTER.md): light Swiss-style layout, trust navy with a muted gold
accent, IBM Plex Sans for text and IBM Plex Mono tabular figures for numbers. Status is never shown by colour alone:
every badge carries an icon and a word.

Blocks are rendered as small HTML fragments through ``st.markdown``. All text goes through :func:`h`, which escapes
HTML and turns ``$`` into an entity so dollar amounts are never parsed as LaTeX.
"""

from __future__ import annotations

from html import escape

import plotly.graph_objects as go
import streamlit as st

from app.engine import ACCOUNT_SHORT, GOAL_LABELS

# --------------------------------------------------------------------------
# Tokens
# --------------------------------------------------------------------------

NAVY = "#1e3a8a"
NAVY_SOFT = "#c7d2fe"
SLATE = "#94a3b8"
GOLD = "#a16207"
INK = "#0f172a"
INK_2 = "#475569"
MUTED = "#64748b"
GRID = "#e5e8ee"
BASELINE = "#cbd2dc"
FONT = "'IBM Plex Sans', system-ui, -apple-system, 'Segoe UI', sans-serif"

CSS = """
<style>
:root {
  --sw-ink: #0f172a; --sw-ink-2: #475569; --sw-muted: #64748b; --sw-line: #dde2ea; --sw-line-soft: #eceff4;
  --sw-surface: #ffffff; --sw-canvas: #f6f7f9; --sw-navy: #1e3a8a; --sw-navy-tint: #eef2ff; --sw-gold: #a16207;
  --sw-good: #166534; --sw-good-bg: #ecfdf3; --sw-good-line: #b7e4c7;
  --sw-bad: #b42318; --sw-bad-bg: #fef3f2; --sw-bad-line: #f4c7c2;
  --sw-warn: #92400e; --sw-warn-bg: #fffaeb; --sw-warn-line: #f3d79a;
  --sw-mono: 'IBM Plex Mono', ui-monospace, SFMono-Regular, Menlo, monospace;
  --sw-radius: 8px;
}
.block-container {padding-top: 4.25rem; padding-bottom: 4rem; max-width: 1360px;}
footer, [data-testid="stDeployButton"] {visibility: hidden;}
.sw-h1 [data-testid="stHeaderActionElements"], .sw-h2 [data-testid="stHeaderActionElements"],
.sw-decision [data-testid="stHeaderActionElements"], .sw-card [data-testid="stHeaderActionElements"] {display: none;}

/* Bordered Streamlit containers read as white cards on the grey canvas. */
[class*="st-key-card"] {background: var(--sw-surface);}
[data-testid="stExpander"] details {background: var(--sw-surface);}
[data-testid="stTabs"] [data-baseweb="tab-list"] {gap: 1.25rem; border-bottom: 1px solid var(--sw-line);}
[data-testid="stTabs"] [data-baseweb="tab"] p {font-weight: 500;}
:focus-visible {outline: 2px solid var(--sw-navy) !important; outline-offset: 2px;}
@media (prefers-reduced-motion: reduce) {* {transition: none !important; animation: none !important;}}

.sw-num {font-family: var(--sw-mono); font-variant-numeric: tabular-nums; letter-spacing: -.01em;}

/* Page header */
.sw-eyebrow {font-size: .72rem; font-weight: 600; letter-spacing: .09em; text-transform: uppercase; color: var(--sw-navy); margin: 0 0 .25rem;}
.sw-h1 {font-size: 1.75rem !important; font-weight: 600 !important; color: var(--sw-ink); line-height: 1.2 !important; margin: 0 !important; padding: 0 !important; letter-spacing: -.015em;}
.sw-lede {color: var(--sw-ink-2); font-size: .95rem; line-height: 1.55; margin: .35rem 0 0; max-width: 78ch;}
.sw-h2 {font-size: 1rem !important; font-weight: 600 !important; color: var(--sw-ink); line-height: 1.4 !important; margin: 1.4rem 0 .15rem !important; padding: 0 !important; letter-spacing: 0;}
[class*="st-key-card"] .sw-h2:first-child {margin-top: 0 !important;}
.sw-h2 + .sw-caption {margin-top: 0;}
.sw-caption {font-size: .82rem; color: var(--sw-muted); line-height: 1.5; margin: .2rem 0 .6rem;}

/* Badges */
.sw-badges {display: flex; flex-wrap: wrap; gap: .4rem; margin-top: .6rem;}
.sw-badge {display: inline-flex; align-items: center; gap: .3rem; padding: .14rem .55rem; border-radius: 999px;
  font-size: .76rem; font-weight: 600; border: 1px solid; white-space: nowrap; line-height: 1.5;}
.sw-badge svg {width: 13px; height: 13px; flex: none;}
.sw-badge.good {color: var(--sw-good); background: var(--sw-good-bg); border-color: var(--sw-good-line);}
.sw-badge.bad {color: var(--sw-bad); background: var(--sw-bad-bg); border-color: var(--sw-bad-line);}
.sw-badge.warn {color: var(--sw-warn); background: var(--sw-warn-bg); border-color: var(--sw-warn-line);}
.sw-badge.neutral {color: var(--sw-ink-2); background: #f1f5f9; border-color: var(--sw-line);}
.sw-badge.info {color: var(--sw-navy); background: var(--sw-navy-tint); border-color: #c7d2fe;}

/* Fact grid (client profile at a glance) */
.sw-facts {display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: .1rem 1.25rem;
  margin: .9rem 0 0; padding: .75rem 0 0; border-top: 1px solid var(--sw-line);}
.sw-facts div {min-width: 0;}
.sw-facts dt {font-size: .7rem; font-weight: 600; letter-spacing: .05em; text-transform: uppercase; color: var(--sw-muted);}
.sw-facts dd {margin: .1rem 0 .4rem; font-size: .9rem; color: var(--sw-ink); overflow-wrap: anywhere;}

/* KPI strip */
.sw-kpis {display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: .75rem; margin: 1rem 0 .25rem;}
.sw-kpi {background: var(--sw-surface); border: 1px solid var(--sw-line); border-radius: var(--sw-radius); padding: .8rem 1rem .75rem; min-width: 0;}
.sw-kpi-label {font-size: .72rem; font-weight: 600; letter-spacing: .05em; text-transform: uppercase; color: var(--sw-muted);}
.sw-kpi-value {font-family: var(--sw-mono); font-variant-numeric: tabular-nums; font-size: 1.5rem; font-weight: 500;
  color: var(--sw-ink); margin: .2rem 0 .1rem; letter-spacing: -.02em; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;}
.sw-kpi-value small {font-size: .85rem; color: var(--sw-muted); font-weight: 400; margin-left: .1rem;}
.sw-kpi-sub {font-size: .8rem; color: var(--sw-ink-2);}
.sw-kpi-sub.good {color: var(--sw-good);} .sw-kpi-sub.bad {color: var(--sw-bad);} .sw-kpi-sub.warn {color: var(--sw-warn);}
.sw-kpi.bad {border-top: 3px solid var(--sw-bad);} .sw-kpi.good {border-top: 3px solid #16a34a;} .sw-kpi.warn {border-top: 3px solid #d97706;}

/* Decision panel */
.sw-decision {background: var(--sw-surface); border: 1px solid var(--sw-line); border-left: 4px solid var(--sw-accent);
  border-radius: var(--sw-radius); padding: 1.1rem 1.25rem 1rem; margin: 1rem 0 .5rem;}
.sw-decision-label {font-size: .72rem; font-weight: 600; letter-spacing: .08em; text-transform: uppercase; color: var(--sw-accent);
  display: flex; align-items: center; gap: .35rem;}
.sw-decision-label svg {width: 14px; height: 14px;}
.sw-decision h2 {font-size: 1.15rem !important; font-weight: 600; color: var(--sw-ink); margin: .3rem 0 .2rem; padding: 0 !important; line-height: 1.4;}
.sw-decision-impact {color: var(--sw-ink-2); font-size: .9rem; margin: 0 0 .9rem;}
.sw-decision-cols {display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 1.5rem;
  border-top: 1px solid var(--sw-line-soft); padding-top: .9rem;}
.sw-decision h3 {font-size: .72rem !important; font-weight: 600; letter-spacing: .06em; text-transform: uppercase;
  color: var(--sw-muted); margin: 0 0 .4rem; padding: 0 !important;}
.sw-decision ul, .sw-decision ol {margin: 0; padding-left: 1.15rem;}
.sw-decision li {font-size: .9rem; line-height: 1.55; color: var(--sw-ink); margin: 0 0 .35rem; max-width: 72ch;}
.sw-guardrail {display: flex; gap: .5rem; align-items: flex-start; margin-top: .9rem; padding: .55rem .75rem;
  background: var(--sw-navy-tint); border-radius: 6px; font-size: .82rem; color: var(--sw-navy);}
.sw-guardrail svg {width: 15px; height: 15px; flex: none; margin-top: .1rem;}

/* Tables */
.sw-table-wrap {overflow-x: auto; border: 1px solid var(--sw-line); border-radius: var(--sw-radius); background: var(--sw-surface);}
table.sw-table {width: 100%; border-collapse: collapse; font-size: .86rem;}
.sw-table th {text-align: left; font-size: .7rem; font-weight: 600; letter-spacing: .05em; text-transform: uppercase;
  color: var(--sw-muted); background: #f8fafc; padding: .55rem .8rem; border-bottom: 1px solid var(--sw-line); white-space: nowrap;}
.sw-table td {padding: .65rem .8rem; border-bottom: 1px solid var(--sw-line-soft); vertical-align: top; color: var(--sw-ink); line-height: 1.45;}
.sw-table tr:last-child td {border-bottom: none;}
.sw-table tr.is-bad td {background: #fffbfa;}
.sw-table tr.is-na td {color: var(--sw-muted);}
.sw-table .sw-rid {font-family: var(--sw-mono); font-weight: 600; color: var(--sw-navy); white-space: nowrap;}
.sw-table .sw-detail {color: var(--sw-bad); font-size: .82rem; margin-top: .2rem;}
.sw-table details {margin-top: .25rem;}
.sw-table summary {cursor: pointer; font-size: .78rem; color: var(--sw-muted); width: fit-content;}
.sw-table summary:hover {color: var(--sw-navy);}
.sw-table details p {font-size: .82rem; color: var(--sw-ink-2); margin: .25rem 0 0; max-width: 70ch;}
.sw-table td.sw-num {white-space: nowrap;}
.sw-arrow {color: var(--sw-muted); margin: 0 .3rem;}

/* Key-value list */
.sw-kv {display: grid; grid-template-columns: minmax(0, auto) minmax(0, 1fr); gap: .45rem 1rem; font-size: .86rem; margin: .25rem 0;}
.sw-kv dt {color: var(--sw-muted);}
.sw-kv.prose dd {font-family: inherit;}
.sw-kv dd {margin: 0; color: var(--sw-ink); font-family: var(--sw-mono); font-variant-numeric: tabular-nums; overflow-wrap: anywhere;}

/* Rule breach bars (client book) */
.sw-bars {display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: .55rem 2rem;}
.sw-bar {display: grid; grid-template-columns: 2.2rem minmax(0, 1fr) 2.4rem; gap: .6rem; align-items: center; font-size: .85rem;}
.sw-bar-title {color: var(--sw-ink); white-space: nowrap; overflow: hidden; text-overflow: ellipsis;}
.sw-bar-track {height: 6px; background: var(--sw-line-soft); border-radius: 3px; margin-top: .3rem; overflow: hidden;}
.sw-bar-fill {height: 100%; background: var(--sw-navy); border-radius: 3px;}
.sw-bar-count {text-align: right; font-family: var(--sw-mono); color: var(--sw-ink);}

/* Callouts and cards */
.sw-callout {display: flex; gap: .6rem; padding: .7rem .9rem; border-radius: var(--sw-radius); border: 1px solid; font-size: .88rem;
  line-height: 1.5; margin: .5rem 0;}
.sw-callout svg {width: 16px; height: 16px; flex: none; margin-top: .15rem;}
.sw-callout.warn {background: var(--sw-warn-bg); border-color: var(--sw-warn-line); color: #78350f;}
.sw-callout.info {background: var(--sw-navy-tint); border-color: #c7d2fe; color: #1e293b;}
.sw-callout.good {background: var(--sw-good-bg); border-color: var(--sw-good-line); color: #14532d;}
.sw-callout.bad {background: var(--sw-bad-bg); border-color: var(--sw-bad-line); color: #7a271a;}
.sw-cards {display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: .75rem;}
.sw-card {background: var(--sw-surface); border: 1px solid var(--sw-line); border-radius: var(--sw-radius); padding: .9rem 1rem;}
.sw-card h4 {font-size: .95rem !important; font-weight: 600; margin: 0 0 .1rem; padding: 0 !important; color: var(--sw-ink);}
.sw-card .sw-card-sub {font-size: .8rem; color: var(--sw-muted); margin: 0 0 .5rem;}
.sw-card p {font-size: .84rem; color: var(--sw-ink-2); line-height: 1.5; margin: .5rem 0 0;}

/* Pipeline steps (methodology) */
.sw-steps {list-style: none; padding: 0; margin: .4rem 0 0; counter-reset: step;}
.sw-steps li {display: grid; grid-template-columns: 2rem minmax(0, 1fr); gap: .75rem; padding: .7rem 0; border-bottom: 1px solid var(--sw-line-soft);}
.sw-steps li:last-child {border-bottom: none;}
.sw-step-n {width: 1.75rem; height: 1.75rem; border-radius: 50%; background: var(--sw-navy-tint); color: var(--sw-navy);
  font: 600 .8rem var(--sw-mono); display: grid; place-items: center;}
.sw-steps strong {color: var(--sw-ink); font-weight: 600;}
.sw-steps .sw-step-meta {font-size: .8rem; color: var(--sw-muted); margin-top: .15rem;}
.sw-steps code {font-family: var(--sw-mono); font-size: .76rem; background: #f1f5f9; color: var(--sw-ink-2); padding: .05rem .35rem; border-radius: 4px;}
.sw-section-label {font-size: .72rem; font-weight: 600; letter-spacing: .08em; text-transform: uppercase; color: var(--sw-navy); margin: 0;}

/* Context bar */
.sw-context {display: flex; flex-wrap: wrap; align-items: center; gap: .35rem .9rem; font-size: .8rem; color: var(--sw-ink-2); min-height: 2.4rem;}
.sw-context b {font-weight: 600; color: var(--sw-ink);}
.sw-context .sw-dot {width: 7px; height: 7px; border-radius: 50%; display: inline-block; margin-right: .35rem; vertical-align: middle;}
.sw-disclaimer {font-size: .76rem; color: var(--sw-muted); margin-top: 2.5rem; padding-top: .9rem; border-top: 1px solid var(--sw-line);}
</style>
"""

# Lucide-style 24px stroke icons. Decorative: every use sits beside visible text.
_ICONS = {
    "check": '<polyline points="20 6 9 17 4 12"/>',
    "x": '<line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>',
    "alert": '<path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/>'
             '<line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>',
    "minus": '<line x1="5" y1="12" x2="19" y2="12"/>',
    "info": '<circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/>',
    "shield": '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>',
    "down": '<line x1="12" y1="5" x2="12" y2="19"/><polyline points="19 12 12 19 5 12"/>',
    "up": '<line x1="12" y1="19" x2="12" y2="5"/><polyline points="5 12 12 5 19 12"/>',
    "user": '<path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>',
}

TONE_ICON = {"good": "check", "bad": "x", "warn": "alert", "neutral": "minus", "info": "info"}


def inject_css() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def icon(name: str) -> str:
    return (f'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" '
            f'stroke-linejoin="round" aria-hidden="true">{_ICONS[name]}</svg>')


def h(text: object) -> str:
    """Escape for HTML, and stop Streamlit's markdown from reading $…$ as LaTeX."""
    return escape(str(text)).replace("$", "&#36;")


def html(fragment: str) -> None:
    st.markdown(fragment, unsafe_allow_html=True)


# --------------------------------------------------------------------------
# Formatting
# --------------------------------------------------------------------------

def money(value: float, decimals: int = 0) -> str:
    return f"${value:,.{decimals}f}"


def compact_money(value: float) -> str:
    if abs(value) >= 1e6:
        return f"${value / 1e6:,.1f}M"
    if abs(value) >= 1e3:
        return f"${value / 1e3:,.0f}K"
    return money(value)


def label(value: str) -> str:
    return str(value).replace("_", " ").title()


def account(value: str) -> str:
    return ACCOUNT_SHORT.get(value, label(value))


def goal(value: str) -> str:
    return GOAL_LABELS.get(value, label(value)).capitalize()


def clean_headline(text: str) -> str:
    return text.replace("✅", "").replace("⚠️", "").strip()


# --------------------------------------------------------------------------
# Badges
# --------------------------------------------------------------------------

def badge(text: str, tone: str, icon_name: str | None = None) -> str:
    return f'<span class="sw-badge {tone}">{icon(icon_name or TONE_ICON[tone])}{h(text)}</span>'


def status_badge(status: str) -> str:
    return badge("Compliant", "good") if status == "PASS" else badge("Flagged", "bad")


def priority_badge(priority: str) -> str:
    return badge(f"{priority} priority", {"High": "bad", "Medium": "warn", "Low": "good"}[priority])


def rule_badge(rule: dict) -> str:
    if not rule["applies"]:
        return badge("N/A", "neutral")
    return badge("Pass", "good") if rule["passed"] else badge("Breach", "bad")


def badges(*items: str) -> str:
    return f'<div class="sw-badges">{"".join(items)}</div>'


# --------------------------------------------------------------------------
# Layout blocks
# --------------------------------------------------------------------------

def page_header(eyebrow: str, title: str, lede: str = "", extra_html: str = "") -> None:
    html(f'<p class="sw-eyebrow">{h(eyebrow)}</p><h1 class="sw-h1">{h(title)}</h1>'
         + (f'<p class="sw-lede">{h(lede)}</p>' if lede else "") + extra_html)


def section(title: str, caption: str = "") -> None:
    html(f'<h2 class="sw-h2">{h(title)}</h2>' + (f'<p class="sw-caption">{h(caption)}</p>' if caption else ""))


def caption(text: str) -> None:
    html(f'<p class="sw-caption">{h(text)}</p>')


def facts(rows: list[tuple[str, str]]) -> str:
    return '<dl class="sw-facts">' + "".join(f"<div><dt>{h(k)}</dt><dd>{h(v)}</dd></div>" for k, v in rows) + "</dl>"


def kpis(items: list[dict]) -> None:
    """items: {label, value, unit?, sub?, sub_tone?, tone?}"""
    cells = []
    for it in items:
        unit = f"<small>{h(it['unit'])}</small>" if it.get("unit") else ""
        sub = f'<div class="sw-kpi-sub {it.get("sub_tone", "")}">{h(it["sub"])}</div>' if it.get("sub") else ""
        cells.append(f'<div class="sw-kpi {it.get("tone", "")}" role="group" aria-label="{h(it["label"])}">'
                     f'<div class="sw-kpi-label">{h(it["label"])}</div>'
                     f'<div class="sw-kpi-value" title="{h(it["value"])}">{h(it["value"])}{unit}</div>{sub}</div>')
    html(f'<div class="sw-kpis">{"".join(cells)}</div>')


def decision(headline: str, impact: str, tone: str, reasons: list[str], actions: list[str],
             guardrail_notes: list[str] | None = None) -> None:
    accent = {"good": "#15803d", "warn": "#b45309", "bad": "#b42318"}[tone]
    label_text = {"good": "Approved", "warn": "Action required", "bad": "Action required · high priority"}[tone]
    action_html = ("<ol>" + "".join(f"<li>{h(a)}</li>" for a in actions) + "</ol>") if actions else \
        "<p class='sw-decision-impact'>No changes needed. Review again at the next annual check-in.</p>"
    guard = ""
    if guardrail_notes:
        guard = f'<div class="sw-guardrail">{icon("shield")}<span><b>Guardrail corrections:</b> {h(" ".join(guardrail_notes))}</span></div>'
    html(
        f'<section class="sw-decision" style="--sw-accent:{accent}" aria-label="Suitability decision">'
        f'<div class="sw-decision-label">{icon(TONE_ICON[tone])}{h(label_text)}</div>'
        f'<h2>{h(clean_headline(headline))}</h2><p class="sw-decision-impact">{h(impact)}</p>'
        f'<div class="sw-decision-cols"><div><h3>Findings</h3><ul>{"".join(f"<li>{h(r)}</li>" for r in reasons)}</ul></div>'
        f'<div><h3>Recommended actions</h3>{action_html}</div></div>{guard}</section>'
    )


def callout(text: str, tone: str = "info", title: str = "") -> None:
    icn = {"warn": "alert", "info": "info", "good": "check", "bad": "x"}[tone]
    head = f"<b>{h(title)}</b> " if title else ""
    html(f'<div class="sw-callout {tone}" role="note">{icon(icn)}<div>{head}{h(text)}</div></div>')


def kv(rows: list[tuple[str, str]], prose: bool = False) -> str:
    return f'<dl class="sw-kv{" prose" if prose else ""}">' + "".join(f"<dt>{h(k)}</dt><dd>{h(v)}</dd>" for k, v in rows) + "</dl>"


def table(headers: list[str], rows: list[list[str]], row_classes: list[str] | None = None,
          num_cols: set[int] | None = None) -> str:
    """Simple accessible HTML table. Cells are pre-rendered HTML; callers escape text with :func:`h`."""
    num_cols = num_cols or set()
    head = "".join(f'<th scope="col">{h(c)}</th>' for c in headers)
    body = []
    for i, row in enumerate(rows):
        cls = f' class="{row_classes[i]}"' if row_classes and row_classes[i] else ""
        body.append(f"<tr{cls}>" + "".join(
            f'<td class="sw-num">{c}</td>' if j in num_cols else f"<td>{c}</td>" for j, c in enumerate(row)) + "</tr>")
    return f'<div class="sw-table-wrap"><table class="sw-table"><thead><tr>{head}</tr></thead><tbody>{"".join(body)}</tbody></table></div>'


def rule_audit_table(rules: list[dict]) -> str:
    rows, classes = [], []
    for r in rules:
        detail = f'<div class="sw-detail">{h(r["details"])}</div>' if r["applies"] and not r["passed"] else ""
        why = f'<details><summary>Why this rule exists</summary><p>{h(r["why"])}</p></details>'
        rows.append([f'<span class="sw-rid">{h(r["rule_id"])}</span>', f"{h(r['title'])}{detail}{why}",
                     h(r["threshold"]), h(r["actual"]), rule_badge(r)])
        classes.append("is-na" if not r["applies"] else ("" if r["passed"] else "is-bad"))
    return table(["Rule", "Check", "Threshold", "Client", "Result"], rows, classes)


def breach_bars(counts: dict[str, int], titles: dict[str, str], total: int) -> str:
    top = max([*counts.values(), 1])
    cells = []
    for rid, n in counts.items():
        cells.append(
            f'<div class="sw-bar"><span class="sw-rid sw-num" style="font-weight:600;color:var(--sw-navy)">{h(rid)}</span>'
            f'<div><div class="sw-bar-title" title="{h(titles[rid])}">{h(titles[rid])}</div>'
            f'<div class="sw-bar-track" aria-hidden="true"><div class="sw-bar-fill" style="width:{n / top * 100:.0f}%"></div></div></div>'
            f'<span class="sw-bar-count" aria-label="{n} of {total} clients">{n}</span></div>')
    return f'<div class="sw-bars">{"".join(cells)}</div>'


# --------------------------------------------------------------------------
# Charts
# --------------------------------------------------------------------------

def _base_layout(fig: go.Figure, height: int, legend: bool = False) -> go.Figure:
    fig.update_layout(
        height=height, margin=dict(l=4, r=20, t=8, b=8),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=FONT, size=12, color=INK_2),
        showlegend=legend, bargap=0.38, bargroupgap=0.1,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0, font=dict(color=INK_2)),
        hoverlabel=dict(bgcolor="white", bordercolor=GRID, font=dict(family=FONT, color=INK, size=12)),
    )
    fig.update_xaxes(gridcolor=GRID, zeroline=True, zerolinecolor=BASELINE, tickfont=dict(color=MUTED), ticksuffix="%")
    fig.update_yaxes(showgrid=False, tickfont=dict(color=INK), autorange="reversed", automargin=True, ticksuffix="  ")
    return fig


def allocation_vs_benchmark(metrics: dict) -> go.Figure:
    aa = metrics["age_allocations"]
    names = ["Equity", "Bonds", "Cash", "Other"]
    actual = [aa["actual_equity_pct"], aa["actual_bond_pct"], aa["actual_cash_pct"], metrics["pct_other"]]
    target = [aa["target_equity_pct"], aa["target_bond_pct"], aa["target_cash_pct"], None]
    fig = go.Figure()
    fig.add_bar(y=names, x=actual, orientation="h", name="Actual", marker=dict(color=NAVY, cornerradius=3),
                hovertemplate="%{y}: %{x:.1f}% actual<extra></extra>")
    fig.add_scatter(y=names[:3], x=target[:3], mode="markers", name="Age benchmark",
                    marker=dict(symbol="line-ns", size=24, line=dict(width=3, color=GOLD)),
                    hovertemplate="%{y}: %{x:.0f}% benchmark<extra></extra>")
    # Value labels sit past whichever is further right, the bar or the benchmark tick, so they never collide.
    fig.add_scatter(y=names, x=[max(a, t or 0) for a, t in zip(actual, target, strict=True)], mode="text",
                    text=[f"  {a:.1f}%" + (f" vs {t:.0f}%" if t is not None else "") for a, t in zip(actual, target, strict=True)],
                    textposition="middle right", textfont=dict(color=INK_2, family=FONT), showlegend=False,
                    hoverinfo="skip", cliponaxis=False)
    fig.update_xaxes(range=[0, 120], tickvals=[0, 20, 40, 60, 80, 100], ticktext=[f"{v}%" for v in range(0, 101, 20)])
    return _base_layout(fig, 230, legend=True)


def distribution_bar(pcts: dict[str, float], formatter=label, height: int | None = None) -> go.Figure:
    items = sorted(pcts.items(), key=lambda kv: -kv[1])
    names = [formatter(k) for k, _ in items]
    values = [v for _, v in items]
    fig = go.Figure(go.Bar(
        y=names, x=values, orientation="h", marker=dict(color=NAVY, cornerradius=3),
        text=[f"{v:.1f}%" for v in values], textposition="outside", textfont=dict(color=INK_2), cliponaxis=False,
        hovertemplate="%{y}: %{x:.1f}%<extra></extra>",
    ))
    fig.update_xaxes(range=[0, max([*values, 10]) * 1.2])
    return _base_layout(fig, height or 56 + 30 * len(items))


def before_after(plan: dict) -> go.Figure:
    names = ["Equity", "Bonds", "Cash", "Other"]
    keys = ["pct_equity", "pct_bond", "pct_cash", "pct_other"]
    before = [plan["before_metrics"][k] for k in keys]
    after = [plan["after_metrics"][k] for k in keys]
    fig = go.Figure()
    for series, values, color in (("Current", before, SLATE), ("Proposed", after, NAVY)):
        fig.add_bar(y=names, x=values, orientation="h", name=series, marker=dict(color=color, cornerradius=3),
                    text=[f"{v:.0f}%" for v in values], textposition="outside", textfont=dict(color=INK_2),
                    cliponaxis=False, hovertemplate=f"%{{y}}: %{{x:.1f}}% ({series.lower()})<extra></extra>")
    fig.update_xaxes(range=[0, 118])
    return _base_layout(fig, 270, legend=True)


PLOTLY_CONFIG = {"displayModeBar": False}
