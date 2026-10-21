"""Client book: triage every client on file with the rules engine."""

from __future__ import annotations

from collections import Counter

import pandas as pd
import streamlit as st

from ui import components as ui
from ui import state


def render() -> None:
    scenario = st.session_state["scenario"]
    book = state.client_book(scenario)
    rules = state.rules()

    ui.page_header(
        "Compliance desk", "Client book",
        f"Rules-engine pre-screen of {len(book)} client portfolios under the {state.SCENARIOS[scenario].lower()} "
        "market scenario. Open a client to run the full nine-agent review.",
    )

    flagged = [r for r in book if r["compliance"]["status"] != "PASS"]
    aum = sum(r["metrics"]["total_value"] for r in book)
    high = sum(1 for r in book if r["priority"] == "High")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Clients reviewed", len(book), border=True)
    c2.metric("Flagged", f"{len(flagged)}", f"{len(flagged) / len(book):.0%} of book", delta_color="off", delta_arrow="off", border=True)
    c3.metric("High priority", high, border=True)
    c4.metric("Assets screened", ui.money(aum / 1e6, 1) + "M", border=True)

    st.markdown("**Breaches by rule**")
    chart_col, key_col = st.columns([3, 2], gap="large")
    counts = Counter(b["rule_id"] for r in book for b in r["compliance"]["breached_rules"])
    ordered = {rid: counts.get(rid, 0) for rid in rules}
    chart_col.plotly_chart(ui.rule_frequency(ordered, {k: v["title"] for k, v in rules.items()}),
                           config=ui.PLOTLY_CONFIG, width="stretch")
    with key_col:
        st.markdown(ui.kv([(rid, r["title"]) for rid, r in rules.items()]), unsafe_allow_html=True)
        st.caption("A client can breach several rules, so bars can sum to more than the flagged count.")

    st.markdown("**Clients**")
    f1, f2, f3 = st.columns([3, 2, 2])
    status = f1.segmented_control("Status", ["All", "Flagged", "Compliant"], default="All")
    risk = f2.multiselect("Risk profile", ["conservative", "moderate", "aggressive"], format_func=ui.label,
                          placeholder="Any")
    query = f3.text_input("Search", placeholder="Name or client ID")

    rows = []
    for r in book:
        p, m = r["profile"], r["metrics"]
        rows.append({
            "ID": p["client_id"], "Client": p["name"], "Age": p["age"], "Goal": ui.goal(p["investment_goal"]),
            "Risk": ui.label(p["stated_risk_tolerance"]), "Portfolio": round(m["total_value"]),
            "Health": r["health_score"], "Priority": r["priority"],
            "Breaches": ", ".join(b["rule_id"] for b in r["compliance"]["breached_rules"]) or "—",
            "Rebalance turnover": r["plan"]["turnover_pct"] / 100,
            "_status": r["compliance"]["status"], "_risk": p["stated_risk_tolerance"],
        })
    df = pd.DataFrame(rows)
    if status == "Flagged":
        df = df[df["_status"] != "PASS"]
    elif status == "Compliant":
        df = df[df["_status"] == "PASS"]
    if risk:
        df = df[df["_risk"].isin(risk)]
    if query:
        q = query.strip().lower()
        df = df[df["Client"].str.lower().str.contains(q, regex=False) | df["ID"].str.lower().str.contains(q, regex=False)]
    df = df.sort_values(["Health", "Portfolio"], ascending=[True, False]).drop(columns=["_status", "_risk"])

    event = st.dataframe(
        df, hide_index=True, width="stretch", height=min(38 + 35 * len(df), 560),
        on_select="rerun", selection_mode="single-row", key="book_table",
        column_config={
            "Portfolio": st.column_config.NumberColumn(format="dollar"),
            "Health": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%d"),
            "Rebalance turnover": st.column_config.NumberColumn(format="percent", help="Share of assets traded by the proposed rebalance"),
            "Age": st.column_config.NumberColumn(width="small"),
            "ID": st.column_config.TextColumn(width="small"),
        },
    )
    st.caption(f"{len(df)} of {len(book)} clients shown · select a row to open the full review.")
    if event.selection.rows:
        st.session_state["client_id"] = df.iloc[event.selection.rows[0]]["ID"]
        del st.session_state["book_table"]  # so returning to the book doesn't bounce straight back
        st.switch_page(st.session_state["pages"]["review"])
