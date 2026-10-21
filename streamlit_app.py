"""ShieldWealth advisor console.

Run with:  uv run streamlit run streamlit_app.py
"""

import streamlit as st

st.set_page_config(page_title="ShieldWealth", page_icon=":material/shield:", layout="wide")

from app.pipeline import gemini_available  # noqa: E402
from ui import components as ui  # noqa: E402
from ui import state  # noqa: E402
from ui.views import book, methodology, onboarding, review  # noqa: E402

state.init()
ui.inject_css()

pages = {
    "book": st.Page(book.render, title="Client book", icon=":material/table_view:", url_path="book", default=True),
    "review": st.Page(review.render, title="Client review", icon=":material/fact_check:", url_path="review"),
    "new": st.Page(onboarding.render, title="New client", icon=":material/person_add:", url_path="new-client"),
    "method": st.Page(methodology.render, title="Methodology", icon=":material/info:", url_path="methodology"),
}
st.session_state["pages"] = pages

st.logo("assets/logo.svg", size="large", icon_image="assets/icon.svg")

nav = st.navigation(list(pages.values()))

with st.sidebar:
    has_key = gemini_available()
    choice = st.segmented_control(
        "Model", ["offline", "gemini"], key="mode_widget", format_func={"offline": "Offline", "gemini": "Gemini"}.get,
        help="Offline runs every agent with a deterministic stand-in model: no API key, no data leaves the machine. "
             "Gemini needs GOOGLE_API_KEY.",
    )
    st.session_state["mode"] = choice or "offline"
    if st.session_state["mode"] == "gemini" and not has_key:
        st.caption(":orange[No GOOGLE_API_KEY set, so reviews run offline.]")
    st.selectbox("Market scenario", list(state.SCENARIOS), key="scenario", format_func=state.SCENARIOS.get,
                 help="Applies to the market scout, risk and planning agents.")
    ctx = state.market(st.session_state["scenario"])
    st.caption(f"VIX {ctx['vix']} · 10Y {ctx['yield_10y']}% · 3M {ctx['yield_3m']}%  \n{ctx['note']}")
    st.divider()
    st.caption("Demonstration system with synthetic client data. Not investment advice.")

nav.run()
