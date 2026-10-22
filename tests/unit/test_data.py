"""Integrity of the demo datasets and the MCP data server's access controls."""

import csv
import json
import os
from itertools import pairwise

import pytest

import mcp_server
from app import engine
from app.engine import DATA_DIR

ACCOUNTS = {"401k", "IRA", "brokerage_taxable", "savings", "checking"}


@pytest.fixture(scope="module")
def holdings_rows():
    with open(os.path.join(DATA_DIR, "holdings.csv"), encoding="utf-8") as f:
        return list(csv.DictReader(f))


@pytest.fixture(scope="module")
def ticker_ref():
    return engine.load_ticker_reference()


class TestDatasets:
    def test_client_ids_unique_and_well_formed(self, all_clients):
        ids = [c["client_id"] for c in all_clients]
        assert len(ids) == len(set(ids)) == 40
        for cid in ids:
            mcp_server.validate_client_id(cid)

    def test_client_fields_valid(self, all_clients):
        for c in all_clients:
            assert not engine.missing_profile_fields(c), c["client_id"]
            assert 18 <= c["age"] <= 100
            assert c["time_horizon_years"] >= 1
            assert c["stated_risk_tolerance"] in {"conservative", "moderate", "aggressive"}
            assert c["liquidity_need"] in {"low", "medium", "high"}
            assert c["credit_score_band"] in {"750_plus", "700_750", "650_700", "below_650"}
            assert c["investment_goal"] in engine.GOAL_LABELS

    def test_every_client_has_holdings(self, all_clients, holdings_rows):
        owners = {r["client_id"] for r in holdings_rows}
        assert {c["client_id"] for c in all_clients} == owners

    def test_holdings_reconcile_with_reference(self, holdings_rows, ticker_ref):
        ids = [r["holding_id"] for r in holdings_rows]
        assert len(ids) == len(set(ids))
        for r in holdings_rows:
            assert r["ticker"] in ticker_ref["tickers"], r["holding_id"]
            assert r["account_type"] in ACCOUNTS, r["holding_id"]
            assert float(r["price_per_share"]) == pytest.approx(ticker_ref["prices"][r["ticker"]], abs=0.01)
            assert float(r["value"]) == pytest.approx(float(r["shares"]) * float(r["price_per_share"]), abs=0.01)
            assert float(r["value"]) > 0

    def test_reference_is_complete(self, ticker_ref):
        assert set(ticker_ref["tickers"]) == set(ticker_ref["prices"])
        for meta in ticker_ref["tickers"].values():
            assert meta["volatility"] in {"none", "low", "low_medium", "medium", "high"}
            assert meta["asset_class"] in {"equity", "equity_fund", "bond_fund", "cash", "real_estate_fund", "alternative"}

    def test_rebalance_destinations_are_classified(self, ticker_ref):
        for t in (*engine.BOND_DESTINATIONS, engine.CASH_DESTINATION, engine.EQUITY_DESTINATION):
            assert t in ticker_ref["tickers"]

    def test_age_brackets_cover_18_to_120_without_gaps(self, norms):
        brackets = sorted(norms, key=lambda b: b["age_min"])
        assert brackets[0]["age_min"] == 18 and brackets[-1]["age_max"] >= 100
        for a, b in pairwise(brackets):
            assert b["age_min"] == a["age_max"] + 1
        for b in brackets:
            assert b["target_equity_pct"] + b["target_bond_pct"] + b["target_cash_pct"] == 100

    def test_every_client_has_a_goal_amount(self, all_clients):
        for c in all_clients:
            assert isinstance(c["goal_amount"], float) and c["goal_amount"] > 0, c["client_id"]

    def test_rules_file_shape(self, rules):
        assert list(rules) == ["R1", "R2", "R3", "R4", "R5", "R6"]
        for r in rules.values():
            assert {"title", "description", "condition", "why", "params", "resolvable_by_rebalance"} <= set(r)

    def test_dataset_covers_every_rule_and_outcome(self, all_clients):
        """The demo book should exercise every rule plus clean passes, so the UI has something to show."""
        seen, passes = set(), 0
        for c in all_clients:
            m = engine.compute_portfolio_metrics(engine.load_holdings(c["client_id"]), c["age"])
            ids = {b["rule_id"] for b in engine.evaluate_compliance(c, m)["breached_rules"]}
            seen |= ids
            passes += not ids
        assert seen == {"R1", "R2", "R3", "R4", "R5", "R6"}
        assert passes >= 10


class TestMcpServer:
    @pytest.mark.parametrize("bad", ["", "  ", "1001", "C", "C12a", "../C001", "C001;DROP", "c001", "*"])
    def test_rejects_malformed_ids(self, bad):
        with pytest.raises(ValueError):
            mcp_server.get_client(bad)
        with pytest.raises(ValueError):
            mcp_server.get_holdings(bad)

    def test_unknown_client(self):
        with pytest.raises(KeyError):
            mcp_server.get_client("C999")

    def test_unknown_client_has_no_holdings(self):
        assert json.loads(mcp_server.get_holdings("C999")) == []

    def test_holdings_scoped_to_one_client(self):
        rows = json.loads(mcp_server.get_holdings("C007"))
        assert rows and {r["client_id"] for r in rows} == {"C007"}

    def test_reference_tools_return_json(self):
        for tool in (mcp_server.get_suitability_rules, mcp_server.get_age_allocation_norms, mcp_server.get_ticker_reference):
            json.loads(tool())
