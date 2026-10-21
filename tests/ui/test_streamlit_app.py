"""Headless smoke tests of the Streamlit app using AppTest.

``st.navigation`` pages are plain functions, so each view is rendered on its own
from a tiny script; the full entry point is exercised by the first test.
"""

import pytest
from streamlit.testing.v1 import AppTest

from tests.conftest import ROOT

VIEW_SCRIPT = """
import os, streamlit as st
os.chdir({root!r})
from ui import components as ui, state
from ui.views import {view}
state.init()
ui.inject_css()
st.session_state.setdefault("pages", {{}})
{view}.render()
"""


def render_view(view: str, **session) -> AppTest:
    at = AppTest.from_string(VIEW_SCRIPT.format(root=ROOT, view=view), default_timeout=90)
    for k, v in session.items():
        at.session_state[k] = v
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def all_text(at: AppTest) -> str:
    return " ".join([*(m.value for m in at.markdown), *(c.value for c in at.caption)])


def test_entry_point_renders_client_book():
    at = AppTest.from_file(f"{ROOT}/streamlit_app.py", default_timeout=90)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    text = all_text(at)
    assert "Client book" in text
    assert 'aria-label="Clients reviewed"' in text and '<div class="sw-kpi-value" title="40">40' in text


def test_client_book_filters():
    at = render_view("book")
    at.text_input[0].input("anderson").run()
    assert not at.exception
    assert "1 of 40 clients shown" in all_text(at)


@pytest.mark.parametrize(("client_id", "expect"), [
    ("C001", "Compliant"), ("C002", "Flagged"), ("C028", "Advisor review"), ("C038", "Compliant"),
])
def test_review_page(client_id, expect):
    at = render_view("review", client_id=client_id)
    text = all_text(at)
    assert expect in text
    assert at.session_state["client_id"] == client_id
    assert [t.label for t in at.tabs] == ["Rule audit", "Portfolio", "Rebalance plan", "Fund research", "Audit trail"]
    assert 'aria-label="Health score"' in text
    assert any(b.label == "Download report" for b in at.get("download_button"))


def test_review_page_under_stress_scenario():
    at = render_view("review", client_id="C013", scenario="stressed")
    assert "VIX" in all_text(at)


def test_onboarding_validates_name():
    at = render_view("onboarding")
    at.button[0].click().run()
    assert any("Enter the client's name" in e.value for e in at.error)


def test_review_page_for_new_client():
    from app import engine
    profile = engine.normalize_profile({
        "client_id": "C9001", "name": "Maria <b>Lopez</b>", "age": 42, "dependents": 1, "investment_goal": "retirement",
        "time_horizon_years": 12, "stated_risk_tolerance": "moderate", "liquidity_need": "medium",
        "employment_status": "employed", "income_stability": "stable", "annual_income": 110000,
        "existing_other_debt": 8000, "existing_mortgage_balance": 0, "net_worth": 150000,
        "credit_score_band": "750_plus", "marital_status": "unspecified",
    })
    holdings = [{"holding_id": "N001", "ticker": "NVDA", "account_type": "brokerage_taxable", "value": 60000.0,
                 "price_per_share": 1.0, "shares": 60000.0},
                {"holding_id": "N002", "ticker": "BND", "account_type": "IRA", "value": 40000.0,
                 "price_per_share": 1.0, "shares": 40000.0}]
    at = render_view("review", client_id="C9001", custom_clients={"C9001": {"profile": profile, "holdings": holdings}})
    header = next(m.value for m in at.markdown if 'class="sw-h1"' in m.value)
    assert "Maria &lt;b&gt;Lopez&lt;/b&gt;" in header and "<b>Lopez</b>" not in header
    assert "R2" in all_text(at)


def test_html_blocks_escape_user_text():
    from ui import components as ui
    out = ui.facts([("Name", "<script>x</script> costs $5 and $6")])
    assert "<script>" not in out and "&lt;script&gt;" in out
    assert "$" not in out  # dollar signs are entities so markdown never renders them as LaTeX


def test_methodology_page():
    at = render_view("methodology")
    text = all_text(at)
    assert "The nine agents" in text and "Guardrails" in text
    assert text.count('class="sw-step-n"') == 9
    assert len(at.dataframe) == 1
