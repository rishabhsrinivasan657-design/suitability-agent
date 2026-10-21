"""Client review: run the nine-agent pipeline for one client and present the results."""

from __future__ import annotations

from html import escape

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

    top_l, top_r = st.columns([4, 1], vertical_alignment="bottom")
    ids = list(options)
    # No widget key: the selection lives in client_id, which other pages also set.
    st.session_state["client_id"] = top_l.selectbox(
        "Client", ids, index=ids.index(st.session_state["client_id"]), format_func=options.get)
    if top_r.button("Re-run review", icon=":material/refresh:", width="stretch"):
        state.clear_review_cache()

    client_id = st.session_state["client_id"]
    try:
        with st.spinner("Running the nine-agent review…"):
            result = state.review(client_id)
    except Exception as e:  # surfaced to the advisor instead of a stack trace
        reason = "Gemini rejected the API key." if "API key not valid" in str(e) else str(e)[:300]
        st.error(f"The review could not finish. {reason}")
        if st.session_state["mode"] == "gemini":
            st.info("Switch the model to **Offline** in the sidebar to run without the Gemini API.")
        return

    if not result.complete:
        st.error("The pipeline stopped before every agent finished. See the agent trace below.")
        _trace_tab(result)
        return

    s = result.state
    profile, metrics, compliance = s["client_profile"], s["portfolio_metrics"], s["compliance_result"]
    summary, plan = s["final_summary"], s["rebalance_plan"]

    st.write("")
    ui.page_header(
        f"Suitability review · {profile['client_id']}",
        profile["name"],
        f"Age {profile['age']} · {ui.goal(profile['investment_goal'])} goal over {profile['time_horizon_years']:g} years · "
        f"{ui.label(profile['stated_risk_tolerance'])} risk · {ui.label(profile['liquidity_need'])} liquidity need",
        ui.status_pill(compliance["status"]) + ui.priority_pill(summary["priority"]),
    )

    applicable = sum(1 for r in compliance["rules"] if r["applies"])
    breaches = len(compliance["breached_rules"])
    stability = s["financial_stability_profile"]
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Portfolio value", ui.money(metrics["total_value"]), f"{metrics['holdings_count']} holdings", delta_color="off", delta_arrow="off", border=True)
    after = plan["after_health_score"]
    k2.metric("Health score", f"{summary['health_score']}/100",
              f"+{after - summary['health_score']} after fix" if after > summary["health_score"] else None, border=True)
    k3.metric("Rules breached", f"{breaches} of {applicable}", "applicable rules", delta_color="off", delta_arrow="off", border=True)
    k4.metric("Equity vs benchmark", f"{metrics['pct_equity']:.0f}%",
              f"{metrics['age_allocations']['equity_diff']:+.0f} pts vs {metrics['age_allocations']['target_equity_pct']:.0f}%",
              delta_color="off", delta_arrow="off", border=True)
    k5.metric("Financial stability", f"{stability['stability_score']}/100", stability["stability_category"], delta_color="off", delta_arrow="off", border=True)

    tone = "good" if compliance["status"] == "PASS" else ("critical" if summary["priority"] == "High" else "warning")
    ui.verdict(summary["headline"], summary["impact"], tone)

    c1, c2 = st.columns(2, gap="large")
    with c1:
        st.markdown("**Why**")
        st.markdown("\n".join(f"- {_md(r)}" for r in summary["reasons"]))
    with c2:
        st.markdown("**Recommended actions**")
        if summary["shifts"]:
            st.markdown("\n".join(f"- {_md(x)}" for x in summary["shifts"]))
        else:
            st.markdown("No changes needed. Review again at the next annual check-in.")
    if s.get("summary_guardrail_notes"):
        st.caption("Guardrail: " + " ".join(s["summary_guardrail_notes"]))

    tabs = st.tabs(["Compliance", "Portfolio", "Rebalance plan", "Fund research", "Agent trace", "Report"])
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
    with tabs[5]:
        _report_tab(result)


def _md(text: str) -> str:
    """Escape characters Streamlit markdown would otherwise interpret (e.g. $…$ as LaTeX)."""
    return text.replace("$", r"\$")


def _compliance_tab(s: dict) -> None:
    rules = s["compliance_result"]["rules"]
    st.caption("Hard suitability rules. Thresholds personalise to the client's age, horizon, risk tolerance, liquidity need and debt.")
    cols = st.columns(3, gap="medium")
    for i, r in enumerate(rules):
        if not r["applies"]:
            badge = ui.pill("Not applicable", "neutral")
        elif r["passed"]:
            badge = ui.pill("Pass", "good")
        else:
            badge = ui.pill("Breach", "critical")
        with cols[i % 3].container(border=True):
            st.markdown(
                f'<div class="sw-rule-head"><span class="sw-rule-id">{r["rule_id"]} · {escape(r["title"])}</span>{badge}</div>'
                + ui.kv([("Threshold", r["threshold"]), ("Actual", r["actual"])])
                + (f'<p class="sw-note" style="color:#9d2323">{escape(r["details"])}</p>' if not r["passed"] else "")
                + f'<p class="sw-note">{escape(r["why"])}</p>',
                unsafe_allow_html=True,
            )

    risk = s["risk_flags"]
    st.markdown("#### Risk-tolerance check")
    st.caption("Advisory comparison of stated risk tolerance against what the portfolio actually holds, in today's market. "
               "These findings don't change the health score.")
    if not risk["findings"]:
        st.markdown(ui.pill(f"Holdings match a {risk['stated_risk']} profile", "good"), unsafe_allow_html=True)
    for f in risk["findings"]:
        tone = {"high": "critical", "medium": "warning", "low": "neutral"}[f["severity"]]
        st.markdown(ui.pill(f["severity"].title(), tone) + escape(f["message"]), unsafe_allow_html=True)


def _portfolio_tab(s: dict) -> None:
    metrics, holdings = s["portfolio_metrics"], s["holdings"]
    left, right = st.columns([3, 2], gap="large")
    with left:
        st.markdown("**Allocation vs. age benchmark**")
        st.plotly_chart(ui.allocation_vs_benchmark(metrics), config=ui.PLOTLY_CONFIG, width="stretch")
    with right:
        st.markdown("**By account**")
        st.plotly_chart(ui.distribution_bar(metrics["account_allocations_pct"], ui.account), config=ui.PLOTLY_CONFIG,
                        width="stretch")
    left, right = st.columns([3, 2], gap="large")
    with left:
        st.markdown("**By sector**")
        st.plotly_chart(ui.distribution_bar(metrics["sector_allocations_pct"]), config=ui.PLOTLY_CONFIG,
                        width="stretch")
    with right:
        st.markdown("**Exposure checks**")
        st.markdown(ui.kv([
            ("Accessible without penalty", f"{metrics['pct_accessible']:.1f}%"),
            ("In retirement accounts", ui.money(metrics["retirement_account_value"])),
            ("High-volatility holdings", f"{metrics['pct_high_volatility']:.1f}%"
             + (f" ({', '.join(metrics['high_volatility_tickers'])})" if metrics["high_volatility_tickers"] else "")),
            ("Largest single bet", f"{metrics['top_position']['ticker'] or '—'} {metrics['top_position']['pct']:.1f}%"),
            ("Largest holding overall", f"{metrics['largest_holding']['ticker']} {metrics['largest_holding']['pct']:.1f}%"),
        ]), unsafe_allow_html=True)
        st.caption("“Single bet” excludes cash and broadly diversified index funds, matching rule R2.")

    st.markdown("**Holdings**")
    df = pd.DataFrame([{
        "Ticker": h["ticker"], "Name": h["asset_name"], "Account": ui.account(h["account_type"]),
        "Class": ui.label(h["asset_class"]), "Sector": ui.label(h["sector"]), "Volatility": ui.label(h["volatility"]),
        "Value": round(h["value"]), "Weight": h["value"] / metrics["total_value"],
    } for h in sorted(holdings, key=lambda h: -h["value"])])
    st.dataframe(df, hide_index=True, width="stretch", column_config={
        "Value": st.column_config.NumberColumn(format="dollar"),
        "Weight": st.column_config.ProgressColumn(min_value=0, max_value=1, format="percent"),
    })


def _rebalance_tab(s: dict) -> None:
    plan = s["rebalance_plan"]
    if not plan["trades"] and not plan["advisor_actions"]:
        st.success("No rebalancing needed: the current portfolio passes every applicable rule.", icon=":material/check_circle:")
        return
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Trades", len(plan["trades"]), border=True)
    k2.metric("Turnover", ui.money(plan["turnover_value"]), f"{plan['turnover_pct']:.1f}% of assets", delta_color="off", delta_arrow="off", border=True)
    k3.metric("Health score after", f"{plan['after_health_score']}/100",
              f"+{plan['after_health_score'] - plan['before_health_score']}", border=True)
    k4.metric("Re-audit", "All clear" if plan["fully_resolved"] else f"{len(plan['after_compliance']['breached_rules'])} open",
              f"{plan['passes']} pass{'es' if plan['passes'] != 1 else ''}", delta_color="off", delta_arrow="off", border=True)

    left, right = st.columns([3, 2], gap="large")
    with left:
        if plan["trades"]:
            st.markdown("**Proposed trades**")
            st.dataframe(pd.DataFrame([{
                "Action": t["action"].title(), "Ticker": t["ticker"],
                "Account": ui.account(t["account_type"]), "Amount": round(t["amount"]), "Fixes": ", ".join(t["rules"]),
            } for t in plan["trades"]]), hide_index=True, width="stretch",
                column_config={"Amount": st.column_config.NumberColumn(format="dollar")})
            st.caption("Proceeds are reinvested inside the account they came from, so no withdrawal or tax-wrapper change is implied. "
                       "Taxable-account sales may realise capital gains.")
        for a in plan["advisor_actions"]:
            st.warning(f"**{a['rule_id']} needs advisor action.** {a['action']}", icon=":material/person:")
    with right:
        st.markdown("**Asset mix: current vs. proposed**")
        st.plotly_chart(ui.before_after(plan), config=ui.PLOTLY_CONFIG, width="stretch")

    with st.expander("Re-audit of the proposed portfolio"):
        st.dataframe(pd.DataFrame([{
            "Rule": f"{b['rule_id']} · {b['title']}",
            "Before": "Breach" if not b["passed"] else ("Pass" if b["applies"] else "N/A"),
            "After": "Breach" if not a["passed"] else ("Pass" if a["applies"] else "N/A"),
            "Actual after": a["actual"],
        } for b, a in zip(plan["before_compliance"]["rules"], plan["after_compliance"]["rules"], strict=True)]),
            hide_index=True, width="stretch")


def _research_tab(s: dict) -> None:
    strategy, rag = s["planning_strategy"], s["product_research_result"]
    st.markdown(f"**Strategy stance:** {ui.label(strategy.get('stance', '—'))}")
    st.markdown(_md(strategy["recommendation"]))
    for d in strategy.get("directives", []):
        st.info(d, icon=":material/insights:")
    st.markdown("**Matching funds**")
    st.caption(f'Vector search over {rag.get("corpus_size", "the")} fund prospectuses for "{rag["query"]}", '
               "filtered to funds the client's risk profile allows.")
    cols = st.columns(max(1, len(rag["matches"])))
    for col, m in zip(cols, rag["matches"], strict=False):
        with col.container(border=True):
            st.markdown(f"**{m['ticker']}** · {m['name']}")
            st.markdown(ui.kv([("Class", ui.label(m["asset_class"])), ("Volatility", ui.label(m["volatility"])),
                               ("Expense ratio", m["expense_ratio"]), ("Match score", f"{m['score']:.2f}")]),
                        unsafe_allow_html=True)
            st.caption(m["objective"])


def _trace_tab(result: ReviewResult) -> None:
    mode = "Gemini" if result.mode == "gemini" else "Offline deterministic model"
    st.caption(f"{mode} · {sum(1 for t in result.trace if t['kind'] == 'tool_call')} tool calls in {result.seconds:.2f}s. "
               "Each agent reads and writes shared session state; none of them call each other directly.")
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


def _report_tab(result: ReviewResult) -> None:
    profile = result.state["client_profile"]
    st.markdown("A client-ready PDF with the verdict, rule-by-rule audit, holdings, proposed trades, fund research and the agent audit trail.")
    st.download_button(
        "Download suitability report (PDF)", data=build_pdf(result.state, result.trace, result.mode),
        file_name=f"ShieldWealth_{profile['client_id']}_{profile['name'].replace(' ', '_')}.pdf",
        mime="application/pdf", type="primary", icon=":material/download:",
    )
