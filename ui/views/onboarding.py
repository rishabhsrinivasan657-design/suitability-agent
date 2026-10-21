"""New client: capture a profile and holdings, then run the same nine-agent review."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from app import engine
from ui import components as ui
from ui import state

GOALS = ["retirement", "home_purchase", "education", "wealth_growth", "income", "capital_preservation"]
ACCOUNTS = ["brokerage_taxable", "401k", "IRA", "savings", "checking"]

STARTER = pd.DataFrame([
    {"Ticker": "VTI", "Account": "401k", "Value ($)": 85000.0},
    {"Ticker": "NVDA", "Account": "brokerage_taxable", "Value ($)": 42000.0},
    {"Ticker": "BND", "Account": "IRA", "Value ($)": 30000.0},
    {"Ticker": "CASH", "Account": "savings", "Value ($)": 12000.0},
])


def render() -> None:
    ui.page_header("Onboarding", "New client review",
                   "Enter a profile and holdings. The client is reviewed by the same nine agents and rules as the client book; "
                   "nothing is written to the client database. Fields marked * are required.")
    ref = state.ticker_reference()
    tickers = sorted(ref["tickers"])

    with st.form("new_client", border=False):
        with st.container(border=True, key="card_profile"):
            ui.html('<p class="sw-section-label">1 · Client profile</p>')
            a, b, c = st.columns(3)
            name = a.text_input("Full name *", placeholder="e.g. Maria Lopez", max_chars=80, autocomplete="name")
            age = b.number_input("Age", 18, 100, 42)
            dependents = c.number_input("Dependents", 0, 12, 1)
            a, b, c = st.columns(3)
            goal = a.selectbox("Investment goal", GOALS, format_func=ui.goal)
            horizon = b.number_input("Time horizon (years)", 1, 50, 12)
            risk = c.selectbox("Risk tolerance", ["conservative", "moderate", "aggressive"], index=1, format_func=ui.label)
        with st.container(border=True, key="card_finances"):
            ui.html('<p class="sw-section-label">2 · Financial position</p>')
            a, b, c = st.columns(3)
            liquidity = a.selectbox("Liquidity need", ["low", "medium", "high"], index=1, format_func=ui.label,
                                    help="How much of the portfolio may be needed in cash at short notice.")
            employment = b.selectbox("Employment", ["employed", "self_employed", "business_owner", "retired", "unemployed"], format_func=ui.label)
            stability = c.selectbox("Income stability", ["stable", "variable"], format_func=ui.label)
            a, b, c, d = st.columns(4)
            income = a.number_input("Annual income ($)", 0, 10_000_000, 110_000, step=5_000)
            debt = b.number_input("Non-mortgage debt ($)", 0, 5_000_000, 8_000, step=1_000)
            mortgage = c.number_input("Mortgage balance ($)", 0, 10_000_000, 0, step=10_000)
            credit = d.selectbox("Credit score", ["750_plus", "700_750", "650_700", "below_650"],
                                 format_func=lambda v: v.replace("_plus", "+").replace("below_", "< ").replace("_", "–"))

        with st.container(border=True, key="card_holdings"):
            ui.html('<p class="sw-section-label">3 · Holdings</p>')
            ui.caption(f"Pick from {len(tickers)} classified securities (use CASH for bank balances). "
                       "Add or delete rows as needed; at least one holding is required.")
            holdings = st.data_editor(
                STARTER, num_rows="dynamic", width="stretch", hide_index=True, key="holdings_editor",
                column_config={
                    "Ticker": st.column_config.SelectboxColumn(options=tickers, required=True),
                    "Account": st.column_config.SelectboxColumn(options=ACCOUNTS, required=True),
                    "Value ($)": st.column_config.NumberColumn(min_value=0.0, step=100.0, format="dollar", required=True),
                },
            )

        submitted = st.form_submit_button("Run nine-agent review", type="primary", icon=":material/play_arrow:")

    if not submitted:
        return
    rows = holdings.dropna(subset=["Ticker", "Account", "Value ($)"])
    rows = rows[rows["Value ($)"] > 0]
    errors = []
    if not name.strip():
        errors.append("Enter the client's name (section 1).")
    if rows.empty:
        errors.append("Add at least one holding with a value above $0 (section 3).")
    if errors:
        st.error("The review can't start yet:\n\n" + "\n".join(f"- {e}" for e in errors), icon=":material/error:")
        return

    client_id = state.next_custom_id()
    profile = engine.normalize_profile({
        "client_id": client_id, "name": name.strip(), "age": age, "dependents": dependents,
        "investment_goal": goal, "time_horizon_years": horizon, "stated_risk_tolerance": risk,
        "liquidity_need": liquidity, "employment_status": employment, "income_stability": stability,
        "annual_income": income, "existing_other_debt": debt, "existing_mortgage_balance": mortgage,
        "net_worth": float(rows["Value ($)"].sum()) - debt - mortgage, "credit_score_band": credit,
        "marital_status": "unspecified",
    })
    staged_holdings = []
    for i, r in enumerate(rows.itertuples(index=False), start=1):
        ticker, acct, value = r[0], r[1], float(r[2])
        price = ref["prices"].get(ticker, 1.0)
        staged_holdings.append({
            "holding_id": f"N{i:03d}", "ticker": ticker, "account_type": acct, "value": round(value, 2),
            "price_per_share": price, "shares": round(value / price, 4),
        })
    st.session_state["custom_clients"][client_id] = {"profile": profile, "holdings": staged_holdings}
    st.session_state["client_id"] = client_id
    st.switch_page(st.session_state["pages"]["review"])
