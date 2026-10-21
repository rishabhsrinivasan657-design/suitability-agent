"""Session settings and cached computations shared by every page."""

from __future__ import annotations

import json

import streamlit as st

from app import engine
from app.pipeline import ReviewResult, gemini_available, run_review

SCENARIOS = {"baseline": "Baseline", "stressed": "Volatility shock", "inverted": "Inverted curve", "live": "Live (Yahoo Finance)"}


def init() -> None:
    ss = st.session_state
    ss.setdefault("client_id", "C002")
    ss.setdefault("mode", "offline")
    ss.setdefault("mode_widget", "offline")
    ss.setdefault("scenario", "baseline")
    ss.setdefault("custom_clients", {})  # client_id -> staged client


@st.cache_data(show_spinner=False)
def clients() -> list[dict]:
    return engine.load_all_clients()


@st.cache_data(show_spinner=False)
def rules() -> dict[str, dict]:
    return engine.load_rules()


@st.cache_data(show_spinner=False)
def ticker_reference() -> dict:
    return engine.load_ticker_reference()


@st.cache_data(show_spinner=False, ttl=300)
def market(scenario: str) -> dict:
    return engine.fetch_live_market_context() if scenario == "live" else engine.scenario_market_context(scenario)


@st.cache_data(show_spinner=False, ttl=300)
def client_book(scenario: str) -> list[dict]:
    """Rules-engine pre-screen of every client on file (no LLM calls)."""
    ctx = market(scenario)
    return [engine.quick_review(c, engine.load_holdings(c["client_id"]), ctx) for c in clients()]


@st.cache_data(show_spinner=False, ttl=600)
def _review(client_id: str, mode: str, scenario: str, staged_json: str | None) -> ReviewResult:
    staged = json.loads(staged_json) if staged_json else None
    return run_review(client_id, mode=mode, market_scenario=scenario, staged_client=staged)


def review(client_id: str) -> ReviewResult:
    ss = st.session_state
    staged = ss["custom_clients"].get(client_id)
    mode = ss["mode"] if ss["mode"] != "gemini" or gemini_available() else "offline"
    return _review(client_id, mode, ss["scenario"], json.dumps(staged, sort_keys=True) if staged else None)


def clear_review_cache() -> None:
    _review.clear()


def client_options() -> dict[str, str]:
    """client_id -> display label, custom clients first."""
    opts = {cid: f"{c['profile']['name']} · new client ({cid})" for cid, c in st.session_state["custom_clients"].items()}
    opts.update({c["client_id"]: f"{c['name']} · {c['client_id']}" for c in clients()})
    return opts


def next_custom_id() -> str:
    used = set(st.session_state["custom_clients"])
    n = 9001
    while f"C{n}" in used:
        n += 1
    return f"C{n}"
