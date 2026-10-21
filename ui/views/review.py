"""Client review: run the nine-agent pipeline for one client and present it as a case file."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from app.agent import AGENT_SPECS
from app.pipeline import ReviewResult
from app.report import build_pdf
from ui import components as ui
from ui import state


def render() -> None:
    options = state.client_options()
    if st.session_state["client_id"] not in options:
        st.session_state["client_id"] = next(iter(options))

    ids = list(options)
    pick, _, rerun = st.columns([3, 2, 1], vertical_alignment="bottom")
    # No widget key: the selection lives in client_id, which other pages also set.
    st.session_state["client_id"] = pick.selectbox(
        "Client", ids, index=ids.index(st.session_state["client_id"]), format_func=options.get)
    if rerun.button("Re-run review", icon=":material/refresh:", width="stretch",
                    help="Discard the cached result and run all nine agents again."):
        state.clear_review_cache()

    client_id = st.session_state["client_id"]
    try:
        with st.spinner("Running the nine-agent review…"):
            result = state.review(client_id)
    except Exception as e:  # surfaced to the advisor instead of a stack trace
        reason = "Gemini rejected the API key." if "API key not valid" in str(e) else str(e)[:300]
        ui.callout(f"The review could not finish. {reason}", "bad", "Review failed.")
        if st.session_state["mode"] == "gemini":
            ui.callout("Switch the model to Offline under Session to run without the Gemini API.", "info")
        return

    if not result.complete:
        ui.callout("The pipeline stopped before every agent finished. The audit trail below shows where.", "bad",
                   "Review incomplete.")
        _trace_tab(result)
        return

    s = result.state
    profile, metrics, compliance = s["client_profile"], s["portfolio_metrics"], s["compliance_result"]
    summary, plan, stability = s["final_summary"], s["rebalance_plan"], s["financial_stability_profile"]

    head_l, head_r = st.columns([4, 1.3], vertical_alignment="top")
    with head_l:
        ui.page_header(
            f"Suitability review · {profile['client_id']}", profile["name"],
            extra_html=ui.badges(ui.status_badge(compliance["status"]), ui.priority_badge(summary["priority"]),
                                 ui.badge(f"{ui.label(profile['stated_risk_tolerance'])} risk", "info")),
        )
    with head_r:
        st.write("")
        st.download_button(
            "Download report", data=build_pdf(result.state, result.trace, result.mode),
            file_name=f"ShieldWealth_{profile['client_id']}_{profile['name'].replace(' ', '_')}.pdf",
            mime="application/pdf", type="primary", icon=":material/picture_as_pdf:", width="stretch",
            help="Client-ready PDF: verdict, rule-by-rule audit, holdings, proposed trades, fund research and agent audit trail.",
        )
    ui.html(ui.facts([
        ("Age", str(profile["age"])),
        ("Goal", ui.goal(profile["investment_goal"])),
        ("Horizon", f"{profile['time_horizon_years']:g} years"),
        ("Liquidity need", ui.label(profile["liquidity_need"])),
        ("Annual income", ui.money(profile.get("annual_income", 0))),
        ("Employment", ui.label(profile.get("employment_status", "—"))),
        ("Dependents", str(profile.get("dependents", "—"))),
    ]))

    applicable = sum(1 for r in compliance["rules"] if r["applies"])
    breaches = len(compliance["breached_rules"])
    after = plan["after_health_score"]
    aa = metrics["age_allocations"]
    ui.kpis([
        {"label": "Portfolio value", "value": ui.money(metrics["total_value"]), "sub": f"{metrics['holdings_count']} holdings"},
        {"label": "Health score", "value": str(summary["health_score"]), "unit": "/100",
         "sub": f"{after}/100 after proposed rebalance" if after > summary["health_score"] else "No change from rebalance",
         "sub_tone": "good" if after > summary["health_score"] else "",
         "tone": "good" if summary["health_score"] == 100 else ("bad" if summary["priority"] == "High" else "warn")},
        {"label": "Rules breached", "value": f"{breaches} of {applicable}", "sub": "applicable rules",
         "sub_tone": "bad" if breaches else "good"},
        {"label": "Equity vs benchmark", "value": f"{metrics['pct_equity']:.0f}%",
         "sub": f"{aa['equity_diff']:+.0f} pts vs {aa['target_equity_pct']:.0f}% age norm"},
        {"label": "Financial stability", "value": str(stability["stability_score"]), "unit": "/100",
         "sub": stability["stability_category"]},
    ])

    tone = "good" if compliance["status"] == "PASS" else ("bad" if summary["priority"] == "High" else "warn")
    ui.decision(summary["headline"], summary["impact"], tone, summary["reasons"], summary["shifts"],
                s.get("summary_guardrail_notes"))

    tabs = st.tabs(["Rule audit", "Portfolio", "Rebalance plan", "Fund research", "Audit trail"])
    with tabs[0]:
        _compliance_tab(s)
    with tabs[1]:
        _portfolio_tab(s)
    with tabs[2]:
        _rebalance_tab(s)
    with tabs[3]:
        _research_tab(s)
    with tabs[4]:
        _trace_tab(result)


def _compliance_tab(s: dict) -> None:
    compliance = s["compliance_result"]
    ui.caption("Hard suitability rules. Thresholds personalise to the client's age, horizon, risk tolerance, "
               "liquidity need and debt.")
    ui.html(ui.rule_audit_table(compliance["rules"]))

    risk = s["risk_flags"]
    ui.section("Risk-tolerance check", "Advisory comparison of stated risk tolerance with what the portfolio holds in "
               "today's market. These findings don't change the health score.")
    if not risk["findings"]:
        ui.callout(f"Holdings match a {risk['stated_risk']} risk profile.", "good")
    for f in risk["findings"]:
        tone = {"high": "bad", "medium": "warn", "low": "info"}[f["severity"]]
        ui.callout(f["message"], tone, f"{f['severity'].title()} severity.")


def _portfolio_tab(s: dict) -> None:
    metrics, holdings = s["portfolio_metrics"], s["holdings"]
    left, right = st.columns([3, 2], gap="large")
    with left:
        ui.section("Allocation vs. age benchmark", "Bars are actual allocation; gold ticks are the age-based norm.")
        st.plotly_chart(ui.allocation_vs_benchmark(metrics), config=ui.PLOTLY_CONFIG, width="stretch")
    with right:
        ui.section("Exposure checks", "“Single bet” excludes cash and broad index funds, matching rule R2.")
        ui.html(ui.kv([
            ("Accessible without penalty", f"{metrics['pct_accessible']:.1f}%"),
            ("In retirement accounts", ui.money(metrics["retirement_account_value"])),
            ("High-volatility holdings", f"{metrics['pct_high_volatility']:.1f}%"
             + (f" ({', '.join(metrics['high_volatility_tickers'])})" if metrics["high_volatility_tickers"] else "")),
            ("Largest single bet", f"{metrics['top_position']['ticker'] or '—'} {metrics['top_position']['pct']:.1f}%"),
            ("Largest holding overall", f"{metrics['largest_holding']['ticker']} {metrics['largest_holding']['pct']:.1f}%"),
        ]))
    left, right = st.columns(2, gap="large")
    with left:
        ui.section("By account")
        st.plotly_chart(ui.distribution_bar(metrics["account_allocations_pct"], ui.account), config=ui.PLOTLY_CONFIG,
                        width="stretch")
    with right:
        ui.section("By sector")
        st.plotly_chart(ui.distribution_bar(metrics["sector_allocations_pct"]), config=ui.PLOTLY_CONFIG, width="stretch")

    ui.section("Holdings", f"{len(holdings)} positions, largest first.")
    df = pd.DataFrame([{
        "Ticker": h["ticker"], "Name": h["asset_name"], "Account": ui.account(h["account_type"]),
        "Class": ui.label(h["asset_class"]), "Sector": ui.label(h["sector"]), "Volatility": ui.label(h["volatility"]),
        "Value": round(h["value"]), "Weight": h["value"] / metrics["total_value"],
    } for h in sorted(holdings, key=lambda h: -h["value"])])
    st.dataframe(df, hide_index=True, width="stretch", column_config={
        "Ticker": st.column_config.TextColumn(width="small"),
        "Value": st.column_config.NumberColumn(format="dollar"),
        "Weight": st.column_config.ProgressColumn(min_value=0, max_value=1, format="percent"),
    })


def _rebalance_tab(s: dict) -> None:
    plan = s["rebalance_plan"]
    if not plan["trades"] and not plan["advisor_actions"]:
        ui.callout("No rebalancing needed: the current portfolio passes every applicable rule.", "good")
        return
    open_after = len(plan["after_compliance"]["breached_rules"])
    ui.kpis([
        {"label": "Trades", "value": str(len(plan["trades"])), "sub": "sells and buys"},
        {"label": "Turnover", "value": ui.money(plan["turnover_value"]), "sub": f"{plan['turnover_pct']:.1f}% of assets"},
        {"label": "Health after", "value": str(plan["after_health_score"]), "unit": "/100",
         "sub": f"+{plan['after_health_score'] - plan['before_health_score']} from {plan['before_health_score']}",
         "sub_tone": "good"},
        {"label": "Re-audit", "value": "All clear" if plan["fully_resolved"] else f"{open_after} open",
         "sub": f"{plan['passes']} pass{'es' if plan['passes'] != 1 else ''} of the rules engine",
         "tone": "good" if plan["fully_resolved"] else "warn"},
    ])

    left, right = st.columns([3, 2], gap="large")
    with left:
        if plan["trades"]:
            ui.section("Proposed trades", "Proceeds are reinvested inside the account they came from, so no withdrawal "
                       "or tax-wrapper change is implied. Taxable-account sales may realise capital gains.")
            ui.html(ui.table(["Action", "Ticker", "Account", "Amount", "Fixes"], [[
                ui.badge(t["action"].title(), "neutral" if t["action"] == "SELL" else "info",
                         "down" if t["action"] == "SELL" else "up"),
                f'<span class="sw-num">{ui.h(t["ticker"])}</span>', ui.h(ui.account(t["account_type"])),
                f'<span style="display:block;text-align:right">{ui.h(ui.money(t["amount"]))}</span>',
                ui.h(", ".join(t["rules"])),
            ] for t in plan["trades"]], num_cols={3}))
        for a in plan["advisor_actions"]:
            ui.callout(a["action"], "warn", f"{a['rule_id']} needs advisor action.")
    with right:
        ui.section("Asset mix: current vs. proposed")
        st.plotly_chart(ui.before_after(plan), config=ui.PLOTLY_CONFIG, width="stretch")

    ui.section("Re-audit of the proposed portfolio", "Every rule is re-run on the post-trade portfolio before the plan "
               "is recommended.")
    rows, classes = [], []
    for b, a in zip(plan["before_compliance"]["rules"], plan["after_compliance"]["rules"], strict=True):
        rows.append([f'<span class="sw-rid">{ui.h(b["rule_id"])}</span>', ui.h(b["title"]),
                     ui.rule_badge(b) + '<span class="sw-arrow" aria-label="becomes">→</span>' + ui.rule_badge(a),
                     ui.h(a["actual"])])
        classes.append("is-bad" if a["applies"] and not a["passed"] else "")
    ui.html(ui.table(["Rule", "Check", "Before → after", "Client after"], rows, classes))


def _research_tab(s: dict) -> None:
    strategy, rag = s["planning_strategy"], s["product_research_result"]
    ui.html(ui.badges(ui.badge(f"Stance: {ui.label(strategy.get('stance', '—'))}", "info")))
    ui.section("Strategy")
    ui.html(f'<p class="sw-lede" style="margin-top:0">{ui.h(strategy["recommendation"])}</p>')
    for d in strategy.get("directives", []):
        ui.callout(d, "info")

    ui.section("Matching funds", f'Vector search over {rag.get("corpus_size", "the")} fund prospectuses for '
               f'"{rag["query"]}", filtered to funds the client\'s risk profile allows.')
    if not rag["matches"]:
        ui.callout("No funds in the corpus fit this risk profile and query.", "info")
        return
    cards = []
    for m in rag["matches"]:
        cards.append(
            f'<article class="sw-card"><h4><span class="sw-num">{ui.h(m["ticker"])}</span></h4>'
            f'<p class="sw-card-sub">{ui.h(m["name"])}</p>'
            + ui.kv([("Class", ui.label(m["asset_class"])), ("Volatility", ui.label(m["volatility"])),
                     ("Expense ratio", m["expense_ratio"]), ("Match score", f"{m['score']:.2f}")])
            + f'<p>{ui.h(m["objective"])}</p></article>')
    ui.html(f'<div class="sw-cards">{"".join(cards)}</div>')


def _trace_tab(result: ReviewResult) -> None:
    mode = "Gemini" if result.mode == "gemini" else "Offline deterministic model"
    calls = sum(1 for t in result.trace if t["kind"] == "tool_call")
    ui.caption(f"{mode} · {calls} tool calls in {result.seconds:.2f}s. Each agent reads and writes shared session "
               "state; none of them call each other directly.")
    by_agent: dict[str, list[dict]] = {}
    for t in result.trace:
        by_agent.setdefault(t["agent"], []).append(t)
    for n, spec in enumerate(AGENT_SPECS, start=1):
        steps = by_agent.get(spec["title"], [])
        failed = any(t["kind"] == "tool_result" and t["detail"].startswith("Error") for t in steps)
        icon = ":material/error:" if failed else (":material/check_circle:" if steps else ":material/radio_button_unchecked:")
        last = next((t["detail"] for t in reversed(steps) if t["kind"] in ("tool_result", "message")), "Did not run")
        with st.expander(f"{n}. {spec['title']} — {last.removeprefix('Success: ')[:110]}", icon=icon):
            for t in steps:
                if t["kind"] == "tool_call":
                    st.markdown(f"`→ {t['name']}({t['detail']})`")
                elif t["kind"] == "tool_result":
                    st.markdown(f"`← {t['name']}`  {_md(t['detail'])}")
                else:
                    st.markdown(f"_{_md(t['detail'])}_")


def _md(text: str) -> str:
    """Escape characters Streamlit markdown would otherwise interpret (e.g. $…$ as LaTeX)."""
    return text.replace("$", r"\$")
