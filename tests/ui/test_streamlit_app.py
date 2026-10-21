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
    assert "Client book" in all_text(at)
    assert {m.label: m.value for m in at.metric}["Clients reviewed"] == "40"


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
    assert len(at.tabs) == 6
    assert any(m.label == "Health score" for m in at.metric)


def test_review_page_under_stress_scenario():
    at = render_view("review", client_id="C013", scenario="stressed")
    assert "VIX" in all_text(at)


def test_onboarding_validates_name():
    at = render_view("onboarding")
    at.button[0].click().run()
    assert any("Enter the client's name" in e.value for e in at.error)


def test_methodology_page():
    at = render_view("methodology")
    assert "The nine agents" in all_text(at)
    assert len(at.dataframe) == 2
