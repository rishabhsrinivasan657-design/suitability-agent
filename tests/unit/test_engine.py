"""Rules engine: metrics, rule boundaries, scoring, rebalancing and summary guardrails."""

import pytest

from app import engine
from tests.conftest import holding, make_profile, portfolio


def audit(profile, holdings):
    metrics = engine.compute_portfolio_metrics(holdings, profile["age"])
    return metrics, engine.evaluate_compliance(profile, metrics)


def breached(result) -> list[str]:
    return [b["rule_id"] for b in result["breached_rules"]]


# --------------------------------------------------------------------------
# Portfolio metrics
# --------------------------------------------------------------------------

class TestMetrics:
    def test_percentages_sum_to_100(self):
        h = portfolio(holding("VTI", 50_000), holding("BND", 30_000, "IRA"), holding("CASH", 20_000, "savings"))
        m = engine.compute_portfolio_metrics(h, 40)
        assert m["total_value"] == 100_000
        assert m["pct_equity"] + m["pct_bond"] + m["pct_cash"] + m["pct_other"] == pytest.approx(100, abs=0.05)
        assert sum(m["asset_allocations_pct"].values()) == pytest.approx(100, abs=0.05)
        assert sum(m["account_allocations_pct"].values()) == pytest.approx(100, abs=0.05)

    def test_same_ticker_across_accounts_aggregates_for_concentration(self):
        h = portfolio(holding("NVDA", 20_000), holding("NVDA", 20_000, "IRA"), holding("CASH", 60_000, "savings"))
        m = engine.compute_portfolio_metrics(h, 40)
        assert m["top_position"] == {"ticker": "NVDA", "pct": 40.0, "value": 40_000}

    def test_cash_and_diversified_funds_are_not_concentration_bets(self):
        h = portfolio(holding("CASH", 70_000, "savings"), holding("VTI", 25_000), holding("AAPL", 5_000))
        m = engine.compute_portfolio_metrics(h, 40)
        assert m["top_position"]["ticker"] == "AAPL"
        assert m["largest_holding"]["ticker"] == "CASH"

    def test_no_zero_value_accounts_reported(self):
        m = engine.compute_portfolio_metrics(portfolio(holding("VTI", 1_000)), 40)
        assert m["account_allocations_pct"] == {"brokerage_taxable": 100.0}

    def test_high_volatility_tracking(self):
        h = portfolio(holding("NVDA", 10_000), holding("TSLA", 10_000), holding("BND", 80_000))
        m = engine.compute_portfolio_metrics(h, 40)
        assert m["pct_high_volatility"] == 20.0
        assert m["high_volatility_tickers"] == ["NVDA", "TSLA"]

    def test_zero_portfolio_rejected(self):
        with pytest.raises(ValueError):
            engine.compute_portfolio_metrics(portfolio(holding("VTI", 0)), 40)

    @pytest.mark.parametrize(("age", "equity"), [(18, 85), (29, 85), (30, 75), (49, 65), (55, 55), (69, 45), (70, 30), (100, 30)])
    def test_age_bracket_boundaries(self, age, equity):
        assert engine.age_targets(age)["equity"] == equity

    def test_unknown_ticker_defaults_to_high_volatility_equity(self):
        (h,) = portfolio(holding("ZZZZ", 1_000))
        assert (h["asset_class"], h["volatility"]) == ("equity", "high")

    def test_caller_classification_overrides_reference(self):
        (h,) = portfolio(holding("VTI", 1_000, volatility="high"))
        assert h["volatility"] == "high"


# --------------------------------------------------------------------------
# Rule boundaries
# --------------------------------------------------------------------------

class TestRules:
    def test_clean_portfolio_passes(self):
        _, c = audit(make_profile(), portfolio(holding("VTI", 60_000), holding("BND", 30_000, "IRA"), holding("CASH", 10_000, "savings")))
        assert c["status"] == "PASS"
        assert breached(c) == []
        assert len(c["rules"]) == 6

    @pytest.mark.parametrize(("horizon", "expect"), [(3, True), (3.5, False), (1, True)])
    def test_r1_short_horizon_with_retirement_money(self, horizon, expect):
        p = make_profile(time_horizon_years=horizon, goal_amount=120_000)
        _, c = audit(p, portfolio(holding("BND", 10_000, "401k"), holding("CASH", 90_000, "savings")))
        assert ("R1" in breached(c)) is expect

    @pytest.mark.parametrize(("goal", "expect"), [(90_000, False), (90_001, True)])
    def test_r1_passes_when_accessible_money_covers_the_goal(self, goal, expect):
        p = make_profile(time_horizon_years=2, goal_amount=goal)
        _, c = audit(p, portfolio(holding("BND", 10_000, "401k"), holding("CASH", 90_000, "savings")))
        assert ("R1" in breached(c)) is expect

    @pytest.mark.parametrize(("age", "expect"), [(57, True), (58, False)])
    def test_r1_exempts_clients_59_and_a_half_by_the_goal_date(self, age, expect):
        p = make_profile(age=age, time_horizon_years=2, goal_amount=200_000)  # 57+2=59 < 59.5; 58+2=60
        _, c = audit(p, portfolio(holding("BND", 10_000, "401k"), holding("CASH", 90_000, "savings")))
        assert ("R1" in breached(c)) is expect

    def test_r1_without_goal_amount_flags_conservatively(self):
        _, c = audit(make_profile(time_horizon_years=2), portfolio(holding("BND", 10_000, "401k"), holding("CASH", 90_000, "savings")))
        r1 = next(r for r in c["rules"] if r["rule_id"] == "R1")
        assert not r1["passed"] and "goal amount" in r1["details"].lower()

    def test_r1_breach_explains_the_shortfall(self):
        p = make_profile(time_horizon_years=3, goal_amount=60_000)
        _, c = audit(p, portfolio(holding("BND", 40_000, "401k"), holding("CASH", 25_000, "savings")))
        r1 = next(r for r in c["rules"] if r["rule_id"] == "R1")
        assert "$25,000" in r1["details"] and "$60,000" in r1["details"]

    def test_r1_short_horizon_without_retirement_money_passes(self):
        _, c = audit(make_profile(time_horizon_years=2), portfolio(holding("CASH", 50_000, "savings")))
        assert "R1" not in breached(c)

    @pytest.mark.parametrize(("aapl", "expect"), [(30_000, False), (30_001, True)])
    def test_r2_exactly_at_limit_passes(self, aapl, expect):
        _, c = audit(make_profile(), portfolio(holding("AAPL", aapl), holding("BND", 100_000 - aapl)))
        assert ("R2" in breached(c)) is expect

    @pytest.mark.parametrize(("tolerance", "nvda", "expect"), [
        ("conservative", 15_000, False), ("conservative", 15_100, True), ("moderate", 40_000, False),
    ])
    def test_r3_only_for_conservative(self, tolerance, nvda, expect):
        _, c = audit(make_profile(stated_risk_tolerance=tolerance), portfolio(holding("NVDA", nvda), holding("BND", 100_000 - nvda)))
        assert ("R3" in breached(c)) is expect

    @pytest.mark.parametrize(("need", "accessible", "expect"), [
        ("high", 25_000, False), ("high", 24_000, True), ("medium", 0, False),
    ])
    def test_r4_accessible_floor(self, need, accessible, expect):
        h = [holding("BND", 100_000 - accessible, "401k")] + ([holding("CASH", accessible, "savings")] if accessible else [])
        _, c = audit(make_profile(liquidity_need=need), portfolio(*h))
        assert ("R4" in breached(c)) is expect

    @pytest.mark.parametrize(("debt", "nvda", "expect"), [
        (20_000, 25_000, False), (20_001, 25_000, True), (50_000, 20_000, False),
    ])
    def test_r5_debt_and_volatility(self, debt, nvda, expect):
        p = make_profile(existing_other_debt=debt, stated_risk_tolerance="aggressive")
        _, c = audit(p, portfolio(holding("NVDA", nvda), holding("VTI", 100_000 - nvda)))
        assert ("R5" in breached(c)) is expect

    @pytest.mark.parametrize(("age", "equity", "expect"), [
        (54, 95_000, False),  # rule starts at 55
        (55, 70_000, False),  # benchmark 55 + 15 = 70, at the ceiling
        (55, 70_100, True),
        (72, 46_000, True),   # benchmark 30 + 15 = 45
    ])
    def test_r6_age_equity_ceiling(self, age, equity, expect):
        _, c = audit(make_profile(age=age), portfolio(holding("VTI", equity), holding("BND", 100_000 - equity)))
        assert ("R6" in breached(c)) is expect

    def test_non_applicable_rules_are_marked(self):
        _, c = audit(make_profile(), portfolio(holding("VTI", 100)))
        applies = {r["rule_id"]: r["applies"] for r in c["rules"]}
        assert applies == {"R1": False, "R2": True, "R3": False, "R4": False, "R5": False, "R6": False}

    def test_rule_parameters_come_from_rules_file(self, rules):
        tweaked = {rid: {**r, "params": dict(r["params"])} for rid, r in rules.items()}
        tweaked["R2"]["params"]["max_position_pct"] = 50.0
        p = make_profile()
        m = engine.compute_portfolio_metrics(portfolio(holding("AAPL", 40_000), holding("BND", 60_000)), p["age"])
        assert "R2" in breached(engine.evaluate_compliance(p, m, rules))
        assert "R2" not in breached(engine.evaluate_compliance(p, m, tweaked))


# --------------------------------------------------------------------------
# Scoring
# --------------------------------------------------------------------------

@pytest.mark.parametrize(("n", "score"), [(0, 100), (1, 85), (3, 55), (6, 10), (7, 0), (10, 0)])
def test_health_score(n, score):
    assert engine.health_score(n) == score


@pytest.mark.parametrize(("ids", "priority"), [
    ([], "Low"), (["R2"], "Medium"), (["R1"], "Medium"), (["R4"], "Medium"),
    (["R3"], "High"), (["R5"], "High"), (["R6"], "High"), (["R1", "R2"], "High"),
])
def test_priority(ids, priority):
    assert engine.priority_for(ids) == priority


class TestStability:
    def test_perfect_profile(self):
        s = engine.analyze_stability(make_profile())
        assert s["stability_score"] == 100 and s["stability_category"] == "High Stability"
        assert s["deductions"] == []

    def test_deductions_stack_and_floor_at_zero(self):
        p = make_profile(income_stability="variable", employment_status="unemployed",
                         existing_other_debt=90_000, annual_income=40_000, credit_score_band="below_650")
        s = engine.analyze_stability(p)
        assert s["stability_score"] == 100 - 15 - 20 - 20 - 25
        assert s["stability_category"] == "Lower Stability"

    def test_zero_income_does_not_divide_by_zero(self):
        s = engine.analyze_stability(make_profile(annual_income=0, existing_other_debt=5_000))
        assert s["other_debt_to_income_pct"] > 0

    def test_high_rates_add_debt_note(self):
        s = engine.analyze_stability(make_profile(existing_other_debt=12_000), {"yield_10y": 4.5})
        assert s["notes"] and "$12,000" in s["notes"][0]


class TestRisk:
    def test_conservative_with_any_high_vol_is_flagged(self):
        p = make_profile(stated_risk_tolerance="conservative")
        m = engine.compute_portfolio_metrics(portfolio(holding("NVDA", 1_000), holding("BND", 99_000)), 40)
        r = engine.assess_risk(p, m, engine.scenario_market_context("baseline"))
        assert r["risk_tolerance_mismatch"]

    def test_aggressive_under_invested(self):
        p = make_profile(stated_risk_tolerance="aggressive")
        m = engine.compute_portfolio_metrics(portfolio(holding("CASH", 90_000, "savings"), holding("VTI", 10_000)), 30)
        r = engine.assess_risk(p, m)
        assert any("an aggressive investor" in msg for msg in r["mismatches"])

    def test_elevated_vix_raises_severity(self):
        p = make_profile(stated_risk_tolerance="moderate")
        m = engine.compute_portfolio_metrics(portfolio(holding("NVDA", 40_000), holding("BND", 60_000)), 40)
        calm = engine.assess_risk(p, m, engine.scenario_market_context("baseline"))
        stressed = engine.assess_risk(p, m, engine.scenario_market_context("stressed"))
        assert calm["findings"][0]["severity"] == "medium"
        assert stressed["findings"][0]["severity"] == "high"


class TestMarket:
    @pytest.mark.parametrize(("scenario", "vix_level", "curve"), [
        ("baseline", "moderate", "normal_curve"), ("stressed", "elevated", "normal_curve"),
        ("inverted", "elevated", "inverted_curve"),
    ])
    def test_scenarios_classify(self, scenario, vix_level, curve):
        ctx = engine.scenario_market_context(scenario)
        assert (ctx["vix_level"], ctx["rate_environment"]) == (vix_level, curve)

    def test_live_falls_back_when_offline(self, monkeypatch):
        import urllib.request

        def boom(*a, **k):
            raise OSError("offline")

        monkeypatch.setattr(urllib.request, "urlopen", boom)
        ctx = engine.fetch_live_market_context(timeout=0.1)
        assert ctx["source"] == "cached_fallback"
        assert ctx["vix"] == engine.MARKET_SCENARIOS["baseline"]["vix"]


# --------------------------------------------------------------------------
# Rebalancing
# --------------------------------------------------------------------------

class TestRebalance:
    def test_compliant_portfolio_needs_no_trades(self):
        h = portfolio(holding("VTI", 60_000), holding("BND", 40_000))
        plan = engine.propose_rebalance(make_profile(), h)
        assert plan["trades"] == [] and plan["passes"] == 0 and plan["fully_resolved"]

    def test_concentration_is_trimmed_to_target(self):
        h = portfolio(holding("NVDA", 60_000), holding("BND", 40_000))
        plan = engine.propose_rebalance(make_profile(stated_risk_tolerance="aggressive"), h)
        assert plan["fully_resolved"]
        assert plan["after_metrics"]["position_pct"]["NVDA"] == pytest.approx(25.0, abs=0.1)

    def test_trades_preserve_total_value(self):
        h = portfolio(holding("NVDA", 50_000), holding("TSLA", 30_000, "IRA"), holding("CASH", 20_000, "savings"))
        plan = engine.propose_rebalance(make_profile(stated_risk_tolerance="conservative"), h)
        assert plan["after_metrics"]["total_value"] == pytest.approx(100_000, abs=1)
        sells = sum(t["amount"] for t in plan["trades"] if t["action"] == "SELL")
        buys = sum(t["amount"] for t in plan["trades"] if t["action"] == "BUY")
        assert sells == pytest.approx(buys, abs=2)

    def test_proceeds_stay_in_their_account(self):
        h = portfolio(holding("NVDA", 50_000, "IRA"), holding("BND", 50_000, "brokerage_taxable"))
        plan = engine.propose_rebalance(make_profile(stated_risk_tolerance="conservative"), h)
        before = plan["before_metrics"]["account_allocations_pct"]
        after = plan["after_metrics"]["account_allocations_pct"]
        assert before == pytest.approx(after, abs=0.05)

    def test_short_horizon_proceeds_go_to_cash(self):
        p = make_profile(stated_risk_tolerance="conservative", time_horizon_years=2)
        plan = engine.propose_rebalance(p, portfolio(holding("TSLA", 60_000), holding("CASH", 40_000, "savings")))
        buys = {t["ticker"] for t in plan["trades"] if t["action"] == "BUY"}
        assert buys == {engine.CASH_DESTINATION}

    def test_structural_rules_become_advisor_actions(self):
        p = make_profile(time_horizon_years=2, liquidity_need="high", goal_amount=50_000)
        plan = engine.propose_rebalance(p, portfolio(holding("BND", 90_000, "401k"), holding("CASH", 10_000, "savings")))
        assert {a["rule_id"] for a in plan["advisor_actions"]} == {"R1", "R4"}
        assert plan["trades"] == [] and not plan["fully_resolved"]

    def test_every_demo_client_rebalance_clears_tradeable_rules(self, all_clients):
        for client in all_clients:
            plan = engine.propose_rebalance(client, engine.load_holdings(client["client_id"]))
            left = {b["rule_id"] for b in plan["after_compliance"]["breached_rules"]}
            assert left <= {"R1", "R4"}, f"{client['client_id']} still breaches {left}"
            assert plan["after_health_score"] >= plan["before_health_score"]
            assert all(t["amount"] > 0 for t in plan["trades"])


# --------------------------------------------------------------------------
# Strategy, summary and guardrail
# --------------------------------------------------------------------------

def full_state(client_id: str, scenario: str = "baseline") -> dict:
    profile = engine.load_client(client_id)
    holdings = engine.load_holdings(client_id)
    market = engine.scenario_market_context(scenario)
    metrics = engine.compute_portfolio_metrics(holdings, profile["age"])
    compliance = engine.evaluate_compliance(profile, metrics)
    plan = engine.propose_rebalance(profile, holdings)
    stability = engine.analyze_stability(profile, market)
    return {
        "client_profile": profile, "market_context": market, "portfolio_metrics": metrics,
        "compliance_result": compliance, "rebalance_plan": plan, "financial_stability_profile": stability,
        "planning_strategy": engine.build_strategy(profile, stability, metrics, market, compliance, plan),
    }


class TestSummary:
    def test_summary_is_about_the_right_client(self, all_clients):
        """Regression: the old demo model told every client except C001 about James Anderson's house purchase."""
        others = {c["name"].split()[0] for c in all_clients}
        for client in all_clients:
            state = full_state(client["client_id"])
            s = engine.draft_advisor_summary(state)
            owned = {h["ticker"] for h in engine.load_holdings(client["client_id"])}
            sold = {t["ticker"] for t in state["rebalance_plan"]["trades"] if t["action"] == "SELL"}
            assert sold <= owned
            text = " ".join([s["headline"], *s["reasons"], *s["shifts"]])
            assert not {n for n in others - {client["name"].split()[0]} if f"{n}'s" in text}
            if client["investment_goal"] != "home_purchase":
                assert "house" not in text.lower()

    def test_score_and_priority_match_compliance(self, all_clients):
        for client in all_clients:
            state = full_state(client["client_id"])
            s = engine.draft_advisor_summary(state)
            ids = [b["rule_id"] for b in state["compliance_result"]["breached_rules"]]
            assert s["health_score"] == engine.health_score(len(ids))
            assert s["priority"] == engine.priority_for(ids)

    def test_inverted_curve_changes_strategy(self):
        calm = full_state("C008", "baseline")["planning_strategy"]
        inverted = full_state("C008", "inverted")["planning_strategy"]
        assert not calm["directives"]
        assert any("inverted" in d.lower() for d in inverted["directives"])

    def test_guardrail_restores_computed_fields(self):
        draft = engine.draft_advisor_summary(full_state("C002"))
        tampered = {**draft, "health_score": 99, "priority": "Low", "headline": "Friendly rewrite"}
        final, notes = engine.reconcile_summary(tampered, draft)
        assert final["health_score"] == draft["health_score"]
        assert final["priority"] == "High"
        assert final["headline"] == "Friendly rewrite"
        assert len(notes) == 2

    def test_guardrail_ignores_malformed_lists(self):
        draft = engine.draft_advisor_summary(full_state("C002"))
        final, _ = engine.reconcile_summary({"reasons": "not a list", "shifts": [1, 2]}, draft)
        assert final["reasons"] == draft["reasons"] and final["shifts"] == draft["shifts"]

    def test_guardrail_rejects_invented_dollar_amount_and_ticker(self):
        draft = engine.draft_advisor_summary(full_state("C002"))
        final, notes = engine.reconcile_summary({**draft, "headline": "Rebalance: move $1 out of AAPL."}, draft)
        assert final["headline"] == draft["headline"]
        assert any("headline" in n for n in notes)

    def test_guardrail_rejects_approval_claim_on_flagged_client(self):
        draft = engine.draft_advisor_summary(full_state("C002"))
        assert draft["status"] != "PASS"
        final, notes = engine.reconcile_summary({**draft, "headline": "Approved: your portfolio looks great."}, draft)
        assert final["headline"] == draft["headline"]
        assert notes

    def test_guardrail_allows_approval_wording_for_compliant_client(self):
        draft = engine.draft_advisor_summary(full_state("C001"))
        assert draft["status"] == "PASS"
        final, notes = engine.reconcile_summary({**draft, "headline": "Approved: no changes needed."}, draft)
        assert final["headline"] == "Approved: no changes needed." and not notes

    def test_guardrail_rejects_invented_numbers_in_reasons(self):
        draft = engine.draft_advisor_summary(full_state("C002"))
        reasons = ["All good, 0% risk.", *draft["reasons"][1:]]
        final, notes = engine.reconcile_summary({**draft, "reasons": reasons}, draft)
        assert final["reasons"] == draft["reasons"]
        assert any("reasons" in n for n in notes)

    def test_guardrail_rejects_dropped_findings(self):
        draft = engine.draft_advisor_summary(full_state("C002"))
        final, notes = engine.reconcile_summary({**draft, "reasons": ["Everything is fine."]}, draft)
        assert final["reasons"] == draft["reasons"]
        assert notes

    def test_guardrail_keeps_faithful_rewording(self):
        draft = engine.draft_advisor_summary(full_state("C002"))
        reworded = [f"In plain terms: {r}" for r in draft["reasons"]]
        shifts = [s.replace("Sell", "Sell about") for s in draft["shifts"]]
        final, notes = engine.reconcile_summary({**draft, "reasons": reworded, "shifts": shifts}, draft)
        assert final["reasons"] == reworded and final["shifts"] == shifts and not notes
