"""How the system works: agents, rules, data and guardrails."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from app.agent import AGENT_SPECS
from ui import components as ui
from ui import state

STATE_WRITES = {
    "intake_agent": "client_profile",
    "market_scout_agent": "market_context",
    "personal_financial_analyst_agent": "financial_stability_profile",
    "portfolio_analysis_agent": "portfolio_metrics, holdings",
    "risk_assessment_agent": "risk_flags",
    "compliance_agent": "compliance_result",
    "planning_strategy_agent": "rebalance_plan, planning_strategy",
    "product_research_agent": "product_research_result",
    "advisor_summary_agent": "final_summary",
}


def render() -> None:
    ui.page_header("Methodology", "How a review works",
                   "Nine Google ADK agents run in sequence over shared session state. A deterministic engine does every "
                   "calculation; the language model picks tools and writes the client-facing wording.")

    st.markdown("#### The nine agents")
    st.dataframe(pd.DataFrame([{
        "#": i, "Agent": spec["title"], "Tools": ", ".join(t.__name__ for t in spec["tools"]),
        "Writes to state": STATE_WRITES[spec["name"]],
    } for i, spec in enumerate(AGENT_SPECS, start=1)]), hide_index=True, width="stretch")
    st.caption("Steps 4–6 run as a nested `portfolio_review_stage`. The planning agent's rebalance plan is re-audited "
               "against all six rules before it is saved, up to four passes.")

    st.markdown("#### Suitability rules")
    st.dataframe(pd.DataFrame([{
        "Rule": rid, "Check": r["title"], "Condition": r["condition"],
        "Fixable by trading": "Yes" if r["resolvable_by_rebalance"] else "No, advisor action", "Why it exists": r["why"],
    } for rid, r in state.rules().items()]), hide_index=True, width="stretch")
    st.caption("Health score = 100 − 15 per breached rule. Priority is High for two or more breaches or any breach of "
               "R3, R5 or R6; Medium for one other breach; Low when compliant.")

    st.markdown("#### Guardrails")
    st.markdown(
        "- **Numbers come from code, not the model.** Allocation maths, rule verdicts, health score, priority and trades are "
        "computed in `app/engine.py`.\n"
        "- **Summary reconciliation.** `save_final_summary` compares the model's JSON with the engine's draft and restores "
        "any computed field the model changed. Corrections are shown under the verdict.\n"
        "- **Suitability-aware retrieval.** Fund search drops funds more volatile than the client's risk profile allows.\n"
        "- **Scoped data access.** The MCP data server only returns one client's records per call and rejects malformed IDs."
    )

    st.markdown("#### Models and data")
    st.markdown(
        "- **Offline mode** swaps Gemini for a deterministic stand-in that drives the same tools, so the full pipeline "
        "runs with no API key and no client data leaves the machine.\n"
        "- **Gemini mode** uses `gemini-2.5-flash` and needs `GOOGLE_API_KEY`. The client profile and analysis are sent to "
        "Google's API.\n"
        "- **Market scenarios** are fixed presets; *Live* pulls VIX and Treasury yields from Yahoo Finance and falls back to "
        "the baseline when offline.\n"
        f"- **Data** is synthetic: {len(state.clients())} demo clients, {len(state.ticker_reference()['tickers'])} classified "
        "tickers with a fixed price snapshot, and 24 fund prospectus summaries indexed with FAISS."
    )
