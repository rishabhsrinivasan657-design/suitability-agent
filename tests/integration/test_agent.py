"""Live Gemini run of the full pipeline.

Costs API calls, so it only runs when RUN_LIVE_TESTS=1 and GOOGLE_API_KEY is set:
    RUN_LIVE_TESTS=1 uv run pytest tests/integration/test_agent.py
"""

import os

import pytest

from app import engine
from app.pipeline import STATE_KEYS, gemini_available, run_review

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LIVE_TESTS") != "1" or not gemini_available(),
    reason="live Gemini test: set RUN_LIVE_TESTS=1 and GOOGLE_API_KEY",
)


def test_gemini_pipeline_end_to_end() -> None:
    result = run_review("C002", mode="gemini")
    assert all(k in result.state for k in STATE_KEYS)
    summary = result.state["final_summary"]
    breaches = result.state["compliance_result"]["breached_rules"]
    # Guardrail: whatever the model wrote, computed fields match the engine.
    assert summary["health_score"] == engine.health_score(len(breaches))
    assert summary["priority"] == engine.priority_for([b["rule_id"] for b in breaches])
