"""Shared Streamlit building blocks: styling, header, status pills and charts."""

from __future__ import annotations

from html import escape

import plotly.graph_objects as go
import streamlit as st

from app.engine import ACCOUNT_SHORT, GOAL_LABELS

# Chart palette (validated categorical slots 1–2, single-hue sequential, reserved status colours).
SERIES_1 = "#2a78d6"
SERIES_2 = "#eb6834"
INK = "#17202c"
INK_2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
BASELINE = "#c3c2b7"
STATUS = {"good": "#0ca30c", "warning": "#fab219", "serious": "#ec835a", "critical": "#d03b3b"}

CSS = """
<style>
.block-container {padding-top: 2.2rem; padding-bottom: 3rem; max-width: 1400px;}
[data-testid="stMetricValue"] {font-size: 1.55rem; font-weight: 600;}
[data-testid="stMetricLabel"] p {font-size: 0.78rem; letter-spacing: .02em; color: #52514e;}
.sw-kicker {font-size: .75rem !important; font-weight: 600; letter-spacing: .08em; text-transform: uppercase; color: #1f4e8c; margin-bottom: .1rem;}
p.sw-title {font-size: 1.85rem !important; font-weight: 650; color: #17202c; line-height: 1.2; margin: 0 0 .1rem 0;}
p.sw-sub {color: #52514e; font-size: .95rem !important; margin: .2rem 0 .6rem 0;}
.sw-pill {display: inline-flex; align-items: center; gap: .35rem; padding: .18rem .6rem; border-radius: 999px;
          font-size: .78rem; font-weight: 600; border: 1px solid; margin-right: .35rem; white-space: nowrap;}
.sw-pill.good {color: #0b6b2f; background: #eaf6ec; border-color: #b9e0c3;}
.sw-pill.critical {color: #9d2323; background: #fbeaea; border-color: #efc1c1;}
.sw-pill.warning {color: #7a4b00; background: #fff5df; border-color: #f3d79a;}
.sw-pill.neutral {color: #52514e; background: #f3f4f6; border-color: #dfe2e7;}
.sw-verdict {border-left: 4px solid var(--sw-accent); padding: .2rem 0 .2rem 1rem; margin: .4rem 0 1rem 0;}
.sw-verdict h3 {font-size: 1.15rem !important; padding: 0 !important; font-weight: 650; margin: 0 0 .2rem 0; color: #17202c;}
.sw-verdict p {margin: 0; color: #52514e; font-size: .9rem !important;}
.sw-rule-head {display: flex; justify-content: space-between; align-items: baseline; gap: .5rem;}
.sw-rule-id {font-weight: 700; color: #17202c;}
.sw-kv {display: grid; grid-template-columns: auto 1fr; gap: .15rem .8rem; font-size: .84rem !important; line-height: 1.4; margin: .5rem 0;}
.sw-kv span:nth-child(odd) {color: #898781;}
.sw-kv span:nth-child(even) {color: #17202c; font-variant-numeric: tabular-nums;}
.stMarkdown p.sw-note, p.sw-note {font-size: .8rem !important; line-height: 1.4; color: #52514e; margin: .35rem 0 0 0;}
.sw-step {font-size: .72rem; font-weight: 700; color: #1f4e8c; letter-spacing: .06em;}
footer, [data-testid="stDeployButton"] {visibility: hidden;}
</style>
"""


def inject_css() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def money(value: float, decimals: int = 0) -> str:
    return f"${value:,.{decimals}f}"


def label(value: str) -> str:
    return str(value).replace("_", " ").title()


def account(value: str) -> str:
    return ACCOUNT_SHORT.get(value, label(value))


def goal(value: str) -> str:
    return GOAL_LABELS.get(value, label(value)).capitalize()


def pill(text: str, tone: str) -> str:
    icon = {"good": "✓", "critical": "✕", "warning": "!", "neutral": "–"}[tone]
    return f'<span class="sw-pill {tone}">{icon} {escape(text)}</span>'


def status_pill(status: str) -> str:
    return pill("Compliant", "good") if status == "PASS" else pill("Flagged", "critical")


def priority_pill(priority: str) -> str:
    tone = {"High": "critical", "Medium": "warning", "Low": "good"}[priority]
    return pill(f"{priority} priority", tone)


def page_header(kicker: str, title: str, subtitle: str = "", pills_html: str = "") -> None:
    st.markdown(
        f'<div class="sw-kicker">{escape(kicker)}</div>'
        f'<p class="sw-title">{escape(title)}</p>'
        + (f'<p class="sw-sub">{escape(subtitle)}</p>' if subtitle else "")
        + (f"<div>{pills_html}</div>" if pills_html else ""),
        unsafe_allow_html=True,
    )


def verdict(headline: str, impact: str, tone: str) -> None:
    accent = {"good": STATUS["good"], "warning": STATUS["warning"], "critical": STATUS["critical"]}[tone]
    clean = headline.replace("✅", "").replace("⚠️", "").strip()
    st.markdown(
        f'<div class="sw-verdict" style="--sw-accent:{accent}"><h3>{escape(clean)}</h3><p>{escape(impact)}</p></div>',
        unsafe_allow_html=True,
    )


def kv(rows: list[tuple[str, str]]) -> str:
    return '<div class="sw-kv">' + "".join(f"<span>{escape(k)}</span><span>{escape(v)}</span>" for k, v in rows) + "</div>"


# --------------------------------------------------------------------------
# Charts
# --------------------------------------------------------------------------

def _base_layout(fig: go.Figure, height: int, legend: bool = False) -> go.Figure:
    fig.update_layout(
        height=height, margin=dict(l=8, r=16, t=8, b=8),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, system-ui, -apple-system, Segoe UI, sans-serif", size=12, color=INK_2),
        showlegend=legend, bargap=0.35, bargroupgap=0.08,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0, font=dict(color=INK_2)),
        hoverlabel=dict(bgcolor="white", bordercolor=GRID, font=dict(color=INK, size=12)),
    )
    fig.update_xaxes(gridcolor=GRID, zeroline=True, zerolinecolor=BASELINE, tickfont=dict(color=MUTED), ticksuffix="%")
    fig.update_yaxes(showgrid=False, tickfont=dict(color=INK_2), autorange="reversed", automargin=True, ticksuffix="  ")
    return fig


def allocation_vs_benchmark(metrics: dict) -> go.Figure:
    aa = metrics["age_allocations"]
    names = ["Equity", "Bonds", "Cash", "Other"]
    actual = [aa["actual_equity_pct"], aa["actual_bond_pct"], aa["actual_cash_pct"], metrics["pct_other"]]
    target = [aa["target_equity_pct"], aa["target_bond_pct"], aa["target_cash_pct"], None]
    fig = go.Figure()
    fig.add_bar(y=names, x=actual, orientation="h", name="Actual", marker=dict(color=SERIES_1, cornerradius=4),
                hovertemplate="%{y}: %{x:.1f}% actual<extra></extra>")
    fig.add_scatter(y=names[:3], x=target[:3], mode="markers", name="Age benchmark",
                    marker=dict(symbol="line-ns", size=26, line=dict(width=3, color=INK)),
                    hovertemplate="%{y}: %{x:.0f}% benchmark<extra></extra>")
    # Value labels sit past whichever is further right, the bar or the benchmark tick, so they never collide.
    fig.add_scatter(y=names, x=[max(a, t or 0) for a, t in zip(actual, target, strict=True)], mode="text",
                    text=[f"  {a:.1f}%" + (f" vs {t:.0f}%" if t is not None else "") for a, t in zip(actual, target, strict=True)],
                    textposition="middle right", textfont=dict(color=INK_2), showlegend=False, hoverinfo="skip",
                    cliponaxis=False)
    fig.update_xaxes(range=[0, 118], tickvals=[0, 20, 40, 60, 80, 100], ticksuffix="%")
    return _base_layout(fig, 230, legend=True)


def distribution_bar(pcts: dict[str, float], formatter=label, height: int | None = None) -> go.Figure:
    items = list(pcts.items())
    names = [formatter(k) for k, _ in items]
    values = [v for _, v in items]
    fig = go.Figure(go.Bar(
        y=names, x=values, orientation="h", marker=dict(color=SERIES_1, cornerradius=4),
        text=[f"{v:.1f}%" for v in values], textposition="outside", textfont=dict(color=INK_2), cliponaxis=False,
        hovertemplate="%{y}: %{x:.1f}%<extra></extra>",
    ))
    fig.update_xaxes(range=[0, max([*values, 10]) * 1.18])
    return _base_layout(fig, height or 60 + 34 * len(items))


def before_after(plan: dict) -> go.Figure:
    names = ["Equity", "Bonds", "Cash", "Other"]
    keys = ["pct_equity", "pct_bond", "pct_cash", "pct_other"]
    before = [plan["before_metrics"][k] for k in keys]
    after = [plan["after_metrics"][k] for k in keys]
    fig = go.Figure()
    for series, values, color in (("Current", before, SERIES_1), ("Proposed", after, SERIES_2)):
        fig.add_bar(y=names, x=values, orientation="h", name=series, marker=dict(color=color, cornerradius=4),
                    text=[f"{v:.0f}%" for v in values], textposition="outside", textfont=dict(color=INK_2),
                    cliponaxis=False, hovertemplate=f"%{{y}}: %{{x:.1f}}% ({series.lower()})<extra></extra>")
    fig.update_xaxes(range=[0, 115])
    return _base_layout(fig, 280, legend=True)


def rule_frequency(counts: dict[str, int], titles: dict[str, str]) -> go.Figure:
    names = list(counts)
    values = list(counts.values())
    fig = go.Figure(go.Bar(
        y=names, x=values, orientation="h", marker=dict(color=SERIES_1, cornerradius=4),
        text=[str(v) for v in values], textposition="outside", textfont=dict(color=INK_2), cliponaxis=False,
        customdata=[titles[r] for r in counts],
        hovertemplate="%{y} · %{customdata}: %{x} clients<extra></extra>",
    ))
    fig.update_xaxes(ticksuffix="", range=[0, max([*values, 1]) * 1.25], showticklabels=False, showgrid=False)
    return _base_layout(fig, 230)


PLOTLY_CONFIG = {"displayModeBar": False}
