"""Suitability review PDF built entirely from pipeline session state."""

from __future__ import annotations

from datetime import datetime

from fpdf import FPDF
from fpdf.enums import XPos, YPos
from fpdf.fonts import FontFace

from app.engine import ACCOUNT_SHORT

INK = (24, 36, 51)
MUTED = (96, 108, 122)
RULE = (214, 220, 228)
ACCENT = (30, 64, 124)
PASS = (26, 127, 75)
FAIL = (176, 42, 42)
WARN = (161, 98, 7)
FILL = (244, 246, 249)

_REPLACEMENTS = {
    "✅": "", "⚠️": "", "⚠": "", "❌": "", "→": "->", "—": "-", "–": "-", "≤": "<=", "≥": ">=",
    "½": " 1/2", "’": "'", "‘": "'", "“": '"', "”": '"', "…": "...", "·": "|", "️": "",
}


def _t(value: object) -> str:
    text = str(value)
    for k, v in _REPLACEMENTS.items():
        text = text.replace(k, v)
    return text.encode("latin-1", "replace").decode("latin-1").strip()


def _account(value: str) -> str:
    return ACCOUNT_SHORT.get(value, _label(value))


def _label(value: str) -> str:
    return _t(str(value).replace("_", " ").title())


class _Report(FPDF):
    def __init__(self, client_label: str):
        super().__init__(format="Letter")
        self.client_label = client_label
        self.set_margins(18, 18, 18)
        self.set_auto_page_break(auto=True, margin=18)

    def header(self) -> None:
        self.set_font("helvetica", "B", 8)
        self.set_text_color(*ACCENT)
        self.cell(0, 5, "SHIELDWEALTH  |  SUITABILITY REVIEW", new_x=XPos.LMARGIN, new_y=YPos.TOP)
        self.set_font("helvetica", "", 8)
        self.set_text_color(*MUTED)
        self.cell(0, 5, _t(self.client_label), align="R", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_draw_color(*RULE)
        self.line(self.l_margin, self.get_y() + 1, self.w - self.r_margin, self.get_y() + 1)
        self.ln(6)

    def footer(self) -> None:
        self.set_y(-13)
        self.set_font("helvetica", "", 7.5)
        self.set_text_color(*MUTED)
        self.cell(0, 5, "Demonstration system with synthetic client data. Not investment advice.",
                  new_x=XPos.LMARGIN, new_y=YPos.TOP)
        self.cell(0, 5, f"Page {self.page_no()}/{{nb}}", align="R")

    def h1(self, text: str) -> None:
        self.ln(2)
        self.set_font("helvetica", "B", 13)
        self.set_text_color(*INK)
        self.cell(0, 8, _t(text), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(1)

    def para(self, text: str, size: float = 9.5, color=MUTED, style: str = "") -> None:
        self.set_font("helvetica", style, size)
        self.set_text_color(*color)
        self.multi_cell(0, 5, _t(text), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    def bullets(self, items: list[str]) -> None:
        self.set_font("helvetica", "", 9.5)
        self.set_text_color(*INK)
        for item in items:
            self.set_x(self.l_margin)
            self.cell(5, 5, "-")
            self.multi_cell(0, 5, _t(item), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    def grid(self, headings: list[str], rows: list[list[str]], widths: tuple, aligns: tuple | None = None,
             status_col: int | None = None) -> None:
        self.set_font("helvetica", "", 8.5)
        self.set_text_color(*INK)
        self.set_draw_color(*RULE)
        self.set_fill_color(255, 255, 255)
        with self.table(col_widths=widths, text_align=aligns or "LEFT", line_height=5.2,
                        headings_style=_heading_style(), borders_layout="HORIZONTAL_LINES",
                        cell_fill_color=FILL, cell_fill_mode="ROWS", padding=1.4) as table:
            table.row([_t(h) for h in headings])
            for row in rows:
                r = table.row()
                for i, value in enumerate(row):
                    if i == status_col:
                        color = {"Pass": PASS, "N/A": MUTED}.get(value, FAIL)
                        r.cell(_t(value), style=FontFace(emphasis="BOLD", color=color))
                    else:
                        r.cell(_t(value))
        self.ln(3)


def _heading_style() -> FontFace:
    return FontFace(emphasis="BOLD", color=INK, fill_color=(226, 231, 238))


def build_pdf(state: dict, trace: list[dict] | None = None, mode: str = "offline") -> bytes:
    profile = state["client_profile"]
    metrics = state["portfolio_metrics"]
    compliance = state["compliance_result"]
    summary = state["final_summary"]
    plan = state.get("rebalance_plan") or {}
    market = state.get("market_context", {})
    stability = state.get("financial_stability_profile", {})
    rag = state.get("product_research_result") or {}
    strategy = state.get("planning_strategy") or {}

    pdf = _Report(f"{profile['name']}  ({profile['client_id']})")
    pdf.alias_nb_pages()
    pdf.add_page()

    # Title block
    pdf.set_font("helvetica", "B", 20)
    pdf.set_text_color(*INK)
    pdf.cell(0, 10, _t(profile["name"]), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.para(
        f"Client {profile['client_id']}  |  Age {profile['age']}  |  {_label(profile['investment_goal'])} goal, "
        f"{profile['time_horizon_years']:g}-year horizon  |  {_label(profile['stated_risk_tolerance'])} risk  |  "
        f"Prepared {datetime.now().strftime('%B %d, %Y')}"
    )
    pdf.ln(4)

    # Verdict band
    status_ok = compliance["status"] == "PASS"
    color = PASS if status_ok else (FAIL if summary["priority"] == "High" else WARN)
    y = pdf.get_y()
    pdf.set_xy(pdf.l_margin + 5, y + 1)
    pdf.set_font("helvetica", "B", 11.5)
    pdf.set_text_color(*INK)
    pdf.multi_cell(0, 6, _t(summary["headline"]), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_x(pdf.l_margin + 5)
    pdf.set_font("helvetica", "", 9.5)
    pdf.set_text_color(*MUTED)
    pdf.cell(0, 6, _t(
        f"Health score {summary['health_score']}/100   |   Priority {summary['priority']}   |   "
        f"Status {'Pass' if status_ok else 'Flagged'}   |   Portfolio ${metrics['total_value']:,.0f}"
    ), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_fill_color(*color)
    pdf.rect(pdf.l_margin, y, 1.6, pdf.get_y() - y + 1, "F")
    pdf.ln(3)

    pdf.h1("Key findings")
    pdf.bullets(summary["reasons"])
    if summary.get("shifts"):
        pdf.h1("Recommended actions")
        pdf.bullets(summary["shifts"])
        pdf.para(summary["impact"], style="I")

    pdf.h1("Client profile")
    pdf.grid(
        ["Item", "Value", "Item", "Value"],
        [
            ["Annual income", f"${profile.get('annual_income', 0):,.0f}", "Net worth", f"${profile.get('net_worth', 0):,.0f}"],
            ["Employment", _label(profile.get("employment_status", "-")), "Income stability", _label(profile.get("income_stability", "-"))],
            ["Liquidity need", _label(profile["liquidity_need"]), "Dependents", str(profile.get("dependents", "-"))],
            ["Other debt", f"${profile.get('existing_other_debt', 0):,.0f}", "Mortgage", f"${profile.get('existing_mortgage_balance', 0):,.0f}"],
            ["Credit band", _t(str(profile.get("credit_score_band", "-")).replace("_", "-")),
             "Stability score", f"{stability.get('stability_score', '-')}/100 ({stability.get('stability_category', '-')})"],
        ],
        widths=(30, 40, 30, 40),
    )

    pdf.add_page()
    pdf.h1("Suitability rules")
    pdf.grid(
        ["Rule", "Check", "Threshold", "Actual", "Result"],
        [[r["rule_id"], r["title"], r["threshold"], r["actual"],
          "Pass" if r["passed"] and r["applies"] else ("N/A" if not r["applies"] else "Breach")]
         for r in compliance["rules"]],
        widths=(10, 38, 44, 44, 16), status_col=4,
    )
    for r in compliance["rules"]:
        if not r["passed"]:
            pdf.para(f"{r['rule_id']}: {r['details']}", color=FAIL, size=9)

    pdf.h1("Allocation vs. age benchmark")
    aa = metrics["age_allocations"]
    pdf.grid(
        ["Asset", "Actual", "Benchmark", "Difference"],
        [[name, f"{aa[f'actual_{k}_pct']:.1f}%", f"{aa[f'target_{k}_pct']:.0f}%", f"{aa[f'{k}_diff']:+.1f} pts"]
         for name, k in (("Equity", "equity"), ("Bonds", "bond"), ("Cash", "cash"))]
        + [["Other (real estate, alternatives)", f"{metrics['pct_other']:.1f}%", "-", "-"]],
        widths=(60, 30, 30, 30), aligns=("LEFT", "RIGHT", "RIGHT", "RIGHT"),
    )

    holdings = state.get("holdings", [])
    if holdings:
        pdf.h1("Holdings")
        rows = sorted(holdings, key=lambda h: -h["value"])
        pdf.grid(
            ["Ticker", "Name", "Account", "Value", "Weight"],
            [[h["ticker"], h["asset_name"][:34], _account(h["account_type"]), f"${h['value']:,.0f}",
              f"{h['value'] / metrics['total_value'] * 100:.1f}%"] for h in rows],
            widths=(16, 62, 32, 28, 18), aligns=("LEFT", "LEFT", "LEFT", "RIGHT", "RIGHT"),
        )

    if plan.get("trades"):
        pdf.add_page()
        pdf.h1("Proposed rebalance")
        pdf.para(
            f"{len(plan['trades'])} trades, ${plan['turnover_value']:,.0f} turnover ({plan['turnover_pct']:.1f}% of assets). "
            f"The proposed portfolio was re-audited against all six rules: health score "
            f"{plan['before_health_score']} -> {plan['after_health_score']}."
        )
        pdf.ln(2)
        pdf.grid(
            ["Action", "Ticker", "Account", "Amount", "Rules"],
            [[t["action"].title(), t["ticker"], _account(t["account_type"]), f"${t['amount']:,.0f}", ", ".join(t["rules"])]
             for t in plan["trades"]],
            widths=(18, 20, 42, 30, 30), aligns=("LEFT", "LEFT", "LEFT", "RIGHT", "LEFT"),
        )
    for action in plan.get("advisor_actions", []):
        pdf.para(f"Advisor action ({action['rule_id']}): {action['action']}", color=INK, size=9)

    if rag.get("matches"):
        pdf.h1("Fund research")
        pdf.para(f"Strategy: {strategy.get('recommendation', '')}")
        pdf.ln(1)
        pdf.grid(
            ["Ticker", "Fund", "Class", "Fee", "Match"],
            [[m["ticker"], m["name"][:40], _label(m["asset_class"]), m["expense_ratio"], f"{m['score']:.2f}"]
             for m in rag["matches"]],
            widths=(16, 74, 28, 16, 16), aligns=("LEFT", "LEFT", "LEFT", "RIGHT", "RIGHT"),
        )

    pdf.h1("Market context")
    pdf.para(
        f"{market.get('scenario_label', '-')}: VIX {market.get('vix', '-')} ({market.get('vix_level', '-')}), "
        f"10-year Treasury {market.get('yield_10y', '-')}%, 3-month Treasury {market.get('yield_3m', '-')}% "
        f"({str(market.get('rate_environment', '-')).replace('_', ' ')}). Source: {market.get('source', '-')}."
    )

    if trace:
        pdf.h1("Agent audit trail")
        pdf.para(
            f"Run mode: {'Gemini' if mode == 'gemini' else 'offline deterministic'}. "
            "Each row is a tool call made by one of the nine agents, in order."
        )
        pdf.ln(1)
        pdf.grid(
            ["#", "Agent", "Tool", "Result"],
            [[str(i + 1), t["agent"], t["name"], t["detail"][:90]]
             for i, t in enumerate(x for x in trace if x["kind"] == "tool_result")],
            widths=(8, 36, 44, 92),
        )

    pdf.h1("Methodology and data handling")
    pdf.para(
        "All figures (allocations, rule results, health score and trades) are computed by a deterministic rules "
        "engine. Language models only choose which tools to run and phrase the summary; a guardrail restores any "
        "computed field a model changes. Client records are synthetic demo data read locally. In Gemini mode the "
        "client profile and analysis are sent to Google's Gemini API; offline mode makes no model calls. Market "
        "data is either a fixed scenario or a live Yahoo Finance quote."
    )
    return bytes(pdf.output())
