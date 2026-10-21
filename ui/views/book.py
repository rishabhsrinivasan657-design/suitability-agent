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
        "market scenario. Select a client to run the full nine-agent review.",
    )

    flagged = [r for r in book if r["compliance"]["status"] != "PASS"]
    aum = sum(r["metrics"]["total_value"] for r in book)
    high = sum(1 for r in book if r["priority"] == "High")
    avg_health = sum(r["health_score"] for r in book) / len(book)
    ui.kpis([
        {"label": "Clients reviewed", "value": str(len(book)), "sub": "rules-engine pre-screen"},
        {"label": "Flagged", "value": str(len(flagged)), "sub": f"{len(flagged) / len(book):.0%} of book",
         "sub_tone": "bad" if flagged else "good", "tone": "bad" if flagged else "good"},
        {"label": "High priority", "value": str(high), "sub": "two+ breaches or a risk rule",
         "tone": "warn" if high else ""},
        {"label": "Average health", "value": f"{avg_health:.0f}", "unit": "/100", "sub": "100 − 15 per breach"},
        {"label": "Assets screened", "value": ui.compact_money(aum), "sub": ui.money(aum)},
    ])

    counts = Counter(b["rule_id"] for r in book for b in r["compliance"]["breached_rules"])
    with st.container(border=True, key="card_breaches"):
        ui.section("Breaches by rule", "Clients breaching each rule. One client can breach several rules.")
        ui.html(ui.breach_bars({rid: counts.get(rid, 0) for rid in rules}, {k: v["title"] for k, v in rules.items()},
                               len(book)))

    ui.section("Review queue", "Sorted by health score, lowest first. Select a row to open the full review.")
    f1, f2, f3, f4 = st.columns([2.2, 2, 2, 2.4], vertical_alignment="bottom")
    status = f1.segmented_control("Status", ["All", "Flagged", "Compliant"], default="All")
    rule_filter = f2.multiselect("Breached rule", list(rules), format_func=lambda r: f"{r} · {rules[r]['title']}",
                                 placeholder="Any rule")
    risk = f3.multiselect("Risk profile", ["conservative", "moderate", "aggressive"], format_func=ui.label,
                          placeholder="Any profile")
    query = f4.text_input("Search", placeholder="Name or client ID", icon=":material/search:")

    rows = []
    for r in book:
        p, m = r["profile"], r["metrics"]
        breached = [b["rule_id"] for b in r["compliance"]["breached_rules"]]
        rows.append({
            "ID": p["client_id"], "Client": p["name"],
            "Status": "Compliant" if r["compliance"]["status"] == "PASS" else "Flagged",
            "Priority": r["priority"], "Health": r["health_score"],
            "Breaches": ", ".join(breached) or "—",
            "Age": p["age"], "Goal": ui.goal(p["investment_goal"]), "Risk": ui.label(p["stated_risk_tolerance"]),
            "Portfolio": round(m["total_value"]), "Turnover": r["plan"]["turnover_pct"] / 100,
            "_breached": breached, "_risk": p["stated_risk_tolerance"],
        })
    df = pd.DataFrame(rows)
    if status in ("Flagged", "Compliant"):
        df = df[df["Status"] == status]
    if rule_filter:
        df = df[df["_breached"].apply(lambda b: any(r in b for r in rule_filter))]
    if risk:
        df = df[df["_risk"].isin(risk)]
    if query:
        q = query.strip().lower()
        df = df[df["Client"].str.lower().str.contains(q, regex=False) | df["ID"].str.lower().str.contains(q, regex=False)]
    df = df.sort_values(["Health", "Portfolio"], ascending=[True, False]).drop(columns=["_breached", "_risk"])

    if df.empty:
        ui.callout("No clients match these filters. Clear a filter to see more of the book.", "info")
        return

    event = st.dataframe(
        df, hide_index=True, width="stretch", height=min(40 + 35 * len(df), 600),
        on_select="rerun", selection_mode="single-row", key="book_table",
        column_config={
            "ID": st.column_config.TextColumn(width="small", pinned=True),
            "Client": st.column_config.TextColumn(pinned=True),
            "Health": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%d", width="small"),
            "Portfolio": st.column_config.NumberColumn(format="dollar"),
            "Turnover": st.column_config.NumberColumn(format="percent", help="Share of assets traded by the proposed rebalance"),
            "Age": st.column_config.NumberColumn(width="small"),
        },
    )
    foot_l, foot_r = st.columns([4, 1], vertical_alignment="center")
    foot_l.caption(f"{len(df)} of {len(book)} clients shown")
    foot_r.download_button("Export CSV", df.to_csv(index=False), file_name="shieldwealth_review_queue.csv",
                           mime="text/csv", icon=":material/download:", width="stretch")
    if event.selection.rows:
        st.session_state["client_id"] = df.iloc[event.selection.rows[0]]["ID"]
        del st.session_state["book_table"]  # so returning to the book doesn't bounce straight back
        st.switch_page(st.session_state["pages"]["review"])
