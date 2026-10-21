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

    left, right = st.columns([3, 2], gap="large")
    with left:
        ui.section("The nine agents", "Steps 4–6 run as a nested portfolio_review_stage. The planning agent's "
                   "rebalance is re-audited against all six rules before it is saved, up to four passes.")
        steps = []
        for i, spec in enumerate(AGENT_SPECS, start=1):
            tools = " ".join(f"<code>{ui.h(t.__name__)}</code>" for t in spec["tools"])
            steps.append(f'<li><span class="sw-step-n" aria-hidden="true">{i}</span><div><strong>{ui.h(spec["title"])}</strong>'
                         f'<div class="sw-step-meta">Tools {tools}</div>'
                         f'<div class="sw-step-meta">Writes <code>{ui.h(STATE_WRITES[spec["name"]])}</code></div></div></li>')
        ui.html(f'<ol class="sw-steps" aria-label="Agent pipeline">{"".join(steps)}</ol>')
    with right:
        ui.section("Guardrails")
        cards = [
            ("Numbers come from code", "Allocation maths, rule verdicts, health score, priority and trades are computed "
             "in app/engine.py, not by the model."),
            ("Profile integrity", "save_client_profile always saves the record get_client fetched from the database. "
             "Any field the model changed is logged and ignored, so it can't alter the inputs to the rules."),
            ("Summary reconciliation", "save_final_summary restores any computed field the model changed and rejects "
             "wording that invents numbers or tickers, claims approval for a flagged client, or drops findings. "
             "Corrections appear in the decision panel."),
            ("Suitability-aware retrieval", "Fund search drops funds more volatile than the client's risk profile allows."),
            ("Scoped data access", "The data server returns one client's records per call and rejects malformed IDs."),
        ]
        ui.html('<div class="sw-cards" style="grid-template-columns:1fr">' + "".join(
            f'<article class="sw-card"><h4>{ui.h(t)}</h4><p style="margin-top:.25rem">{ui.h(d)}</p></article>'
            for t, d in cards) + "</div>")

    ui.section("Suitability rules", "Health score = 100 − 15 per breached rule. Priority is High for two or more "
               "breaches or any breach of R3, R5 or R6; Medium for one other breach; Low when compliant.")
    st.dataframe(pd.DataFrame([{
        "Rule": rid, "Check": r["title"], "Condition": r["condition"],
        "Fixable by trading": "Yes" if r["resolvable_by_rebalance"] else "No, advisor action", "Why it exists": r["why"],
    } for rid, r in state.rules().items()]), hide_index=True, width="stretch",
        column_config={"Rule": st.column_config.TextColumn(width="small"),
                       "Why it exists": st.column_config.TextColumn(width="large")})

    ui.section("Models and data")
    ui.html(ui.kv([
        ("Offline mode", "Deterministic stand-in model; no API key, no data leaves the machine"),
        ("Gemini mode", "gemini-2.5-flash via GOOGLE_API_KEY; profile and analysis are sent to Google"),
        ("Market scenarios", "Fixed presets, or Live (Yahoo Finance) with baseline fallback"),
        ("Clients", f"{len(state.clients())} synthetic demo clients"),
        ("Securities", f"{len(state.ticker_reference()['tickers'])} classified tickers, fixed price snapshot"),
        ("Fund research", "24 fund prospectus summaries indexed with FAISS"),
     ], prose=True).replace('class="sw-kv prose"', 'class="sw-kv prose" style="max-width:820px"'))
