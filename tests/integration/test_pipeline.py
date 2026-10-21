"""End-to-end runs of the nine-agent ADK pipeline with the offline model."""

import pytest

from app import engine
from app.agent import AGENT_SPECS
from app.pipeline import STATE_KEYS, run_review


@pytest.fixture(scope="module")
def book_runs(all_clients):
    return {c["client_id"]: run_review(c["client_id"]) for c in all_clients}


def test_every_client_completes_all_nine_agents(book_runs):
    titles = {spec["title"] for spec in AGENT_SPECS}
    for cid, result in book_runs.items():
        assert result.complete, f"{cid} missing {[k for k in STATE_KEYS if k not in result.state]}"
        assert not result.errors, f"{cid}: {result.errors}"
        assert {t["agent"] for t in result.trace if t["kind"] == "tool_call"} == titles


def test_agents_run_in_order(book_runs):
    order = [spec["title"] for spec in AGENT_SPECS]
    seen = []
    for t in book_runs["C002"].trace:
        if t["kind"] == "tool_call" and (not seen or seen[-1] != t["agent"]):
            seen.append(t["agent"])
    assert seen == order


def test_pipeline_matches_engine(book_runs, all_clients):
    """Whatever the agents do, the saved results must equal a direct engine computation."""
    for client in all_clients:
        state = book_runs[client["client_id"]].state
        holdings = engine.load_holdings(client["client_id"])
        metrics = engine.compute_portfolio_metrics(holdings, client["age"])
        expected = engine.evaluate_compliance(client, metrics)
        assert state["portfolio_metrics"] == metrics
        assert state["compliance_result"]["breached_rules"] == expected["breached_rules"]
        summary = state["final_summary"]
        assert summary["health_score"] == engine.health_score(len(expected["breached_rules"]))
        assert summary["status"] == expected["status"]
        assert state["client_profile"]["client_id"] == client["client_id"]


def test_known_scenarios(book_runs):
    assert book_runs["C001"].state["final_summary"]["status"] == "PASS"
    james = book_runs["C002"].state
    assert [b["rule_id"] for b in james["compliance_result"]["breached_rules"]] == ["R1", "R2", "R3"]
    assert james["final_summary"]["priority"] == "High"
    assert james["product_research_result"]["primary_match"]["asset_class"] in {"cash", "bond_fund"}
    raymond = book_runs["C026"].state  # concentrated employer stock near retirement
    assert {b["rule_id"] for b in raymond["compliance_result"]["breached_rules"]} == {"R2", "R6"}
    assert raymond["rebalance_plan"]["fully_resolved"]


def test_market_scenario_flows_through(all_clients):
    result = run_review("C008", market_scenario="inverted")
    assert result.state["market_context"]["rate_environment"] == "inverted_curve"
    assert any("inverted" in d.lower() for d in result.state["planning_strategy"]["directives"])


def test_staged_custom_client():
    staged = {
        "profile": {
            "client_id": "C9001", "name": "Staged Person", "age": 61, "investment_goal": "retirement",
            "time_horizon_years": 6, "stated_risk_tolerance": "conservative", "liquidity_need": "medium",
            "annual_income": 90000, "existing_other_debt": 0, "credit_score_band": "750_plus",
            "employment_status": "employed", "income_stability": "stable",
        },
        "holdings": [
            {"ticker": "TSLA", "account_type": "brokerage_taxable", "value": 40000},
            {"ticker": "VTI", "account_type": "401k", "value": 50000},
            {"ticker": "CASH", "account_type": "savings", "value": 10000},
        ],
    }
    result = run_review("C9001", staged_client=staged)
    assert result.complete and not result.errors
    assert result.state["client_profile"]["name"] == "Staged Person"
    ids = {b["rule_id"] for b in result.state["compliance_result"]["breached_rules"]}
    assert {"R2", "R3", "R6"} <= ids


def test_unknown_client_stops_cleanly():
    result = run_review("C777")
    assert not result.complete
    assert any("not found" in t["detail"] for t in result.errors)
