"""Deterministic suitability engine.

Every number ShieldWealth shows (allocations, rule verdicts, health score,
rebalancing trades) is computed here. The agents call these functions as
tools and the UI and PDF report read the results back from session state, so
there is exactly one implementation of each calculation.
"""

from __future__ import annotations

import copy
import json
import os
import sys
from collections import defaultdict
from datetime import UTC, datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import mcp_server  # noqa: E402  (needs BASE_DIR on sys.path)

EQUITY_CLASSES = ("equity", "equity_fund")
BOND_CLASSES = ("bond", "bond_fund")
CASH_CLASSES = ("cash",)
ACCESSIBLE_ACCOUNTS = ("savings", "checking", "brokerage_taxable")
RETIREMENT_ACCOUNTS = ("401k", "IRA")
POINTS_PER_BREACH = 15
CRITICAL_RULES = ("R3", "R5", "R6")

# Rebalancing destinations. Proceeds stay inside the account they were sold in.
BOND_DESTINATIONS = ("BND", "AGG")
CASH_DESTINATION = "VMFXX"
EQUITY_DESTINATION = "VXUS"

MARKET_SCENARIOS = {
    "baseline": {
        "label": "Baseline (cached)",
        "vix": 14.5, "yield_10y": 4.25, "yield_3m": 4.05,
        "note": "Calm markets with a normal, gently upward-sloping yield curve.",
    },
    "stressed": {
        "label": "Volatility shock",
        "vix": 34.0, "yield_10y": 4.10, "yield_3m": 3.95,
        "note": "Equity sell-off: VIX above 30, rates roughly unchanged.",
    },
    "inverted": {
        "label": "Inverted curve",
        "vix": 21.5, "yield_10y": 3.85, "yield_3m": 5.10,
        "note": "Short rates above long rates, a classic recession warning.",
    },
}


# --------------------------------------------------------------------------
# Reference data
# --------------------------------------------------------------------------

def load_rules() -> dict[str, dict]:
    return {r["rule_id"]: r for r in json.loads(mcp_server.get_suitability_rules())}


def load_age_norms() -> list[dict]:
    return json.loads(mcp_server.get_age_allocation_norms())["brackets"]


def load_ticker_reference() -> dict:
    return json.loads(mcp_server.get_ticker_reference())


def load_client(client_id: str) -> dict:
    return normalize_profile(json.loads(mcp_server.get_client(client_id)))


def load_holdings(client_id: str) -> list[dict]:
    return enrich_holdings(json.loads(mcp_server.get_holdings(client_id)))


def load_all_clients() -> list[dict]:
    import csv

    with open(os.path.join(DATA_DIR, "clients.csv"), encoding="utf-8") as f:
        return [normalize_profile(row) for row in csv.DictReader(f)]


_INT_FIELDS = ("age", "dependents")
_FLOAT_FIELDS = (
    "annual_income", "net_worth", "existing_mortgage_balance",
    "existing_other_debt", "time_horizon_years",
)
REQUIRED_PROFILE_FIELDS = (
    "client_id", "name", "age", "investment_goal", "time_horizon_years",
    "stated_risk_tolerance", "liquidity_need",
)


def normalize_profile(raw: dict) -> dict:
    """Coerce CSV/JSON strings into typed values and lower-case the enums."""
    profile = dict(raw)
    for key in _INT_FIELDS:
        if key in profile and profile[key] not in (None, ""):
            profile[key] = int(float(profile[key]))
    for key in _FLOAT_FIELDS:
        if key in profile and profile[key] not in (None, ""):
            profile[key] = float(profile[key])
    for key in ("stated_risk_tolerance", "liquidity_need", "investment_goal",
                "employment_status", "income_stability", "credit_score_band"):
        if isinstance(profile.get(key), str):
            profile[key] = profile[key].strip().lower()
    return profile


def missing_profile_fields(profile: dict) -> list[str]:
    return [k for k in REQUIRED_PROFILE_FIELDS if profile.get(k) in (None, "")]


def enrich_holdings(raw: list[dict], ticker_ref: dict | None = None) -> list[dict]:
    """Attach asset class, sector and volatility to each holding.

    Values a caller already set (e.g. a custom holding entered in the UI) win
    over the reference file. A ticker missing from both is treated as a
    high-volatility single stock, the prudent default for a compliance check.
    """
    ref = (ticker_ref or load_ticker_reference())["tickers"]
    enriched = []
    for h in raw:
        ticker = str(h.get("ticker", "")).upper()
        meta = ref.get(ticker, {})
        enriched.append({
            "holding_id": h.get("holding_id", ""),
            "ticker": ticker,
            "asset_name": h.get("asset_name") or meta.get("asset_name", ticker),
            "account_type": h.get("account_type", "brokerage_taxable"),
            "shares": float(h.get("shares") or 0.0),
            "price_per_share": float(h.get("price_per_share") or 0.0),
            "value": float(h["value"]),
            "asset_class": h.get("asset_class") or meta.get("asset_class", "equity"),
            "sector": h.get("sector") or meta.get("sector", "unclassified"),
            "volatility": h.get("volatility") or meta.get("volatility", "high"),
        })
    return enriched


def age_targets(age: int, norms: list[dict] | None = None) -> dict:
    for bracket in norms or load_age_norms():
        if bracket["age_min"] <= age <= bracket["age_max"]:
            return {
                "equity": float(bracket["target_equity_pct"]),
                "bond": float(bracket["target_bond_pct"]),
                "cash": float(bracket["target_cash_pct"]),
            }
    raise ValueError(f"No age bracket covers age {age}")


# --------------------------------------------------------------------------
# Portfolio metrics
# --------------------------------------------------------------------------

def is_concentration_eligible(holding: dict) -> bool:
    """R2 applies to bets on a single issuer or theme.

    Cash equivalents and broadly diversified index funds (sector "diversified")
    already spread risk across hundreds of issuers, so they are exempt.
    """
    return holding["asset_class"] not in CASH_CLASSES and holding["sector"] != "diversified"


def _pct(part: float, total: float) -> float:
    return round(part / total * 100.0, 2) if total else 0.0


def compute_portfolio_metrics(holdings: list[dict], age: int, norms: list[dict] | None = None) -> dict:
    total = sum(h["value"] for h in holdings)
    if total <= 0:
        raise ValueError("Portfolio total value must be greater than zero.")

    by_class: dict[str, float] = defaultdict(float)
    by_sector: dict[str, float] = defaultdict(float)
    by_account: dict[str, float] = defaultdict(float)
    by_position: dict[str, float] = defaultdict(float)
    concentrable: set[str] = set()
    high_vol_value = 0.0
    high_vol_tickers: list[str] = []

    for h in holdings:
        v = h["value"]
        by_class[h["asset_class"]] += v
        by_account[h["account_type"]] += v
        by_position[h["ticker"]] += v
        if is_concentration_eligible(h):
            concentrable.add(h["ticker"])
        if h["sector"] not in ("n/a", ""):
            by_sector[h["sector"]] += v
        if h["volatility"] == "high":
            high_vol_value += v
            if h["ticker"] not in high_vol_tickers:
                high_vol_tickers.append(h["ticker"])

    pct_equity = _pct(sum(by_class[c] for c in EQUITY_CLASSES), total)
    pct_bond = _pct(sum(by_class[c] for c in BOND_CLASSES), total)
    pct_cash = _pct(sum(by_class[c] for c in CASH_CLASSES), total)
    targets = age_targets(age, norms)

    non_cash = {t: v for t, v in by_position.items() if t in concentrable}
    top_ticker = max(non_cash, key=non_cash.get) if non_cash else ""
    largest = max(by_position, key=by_position.get)
    accessible = sum(by_account.get(a, 0.0) for a in ACCESSIBLE_ACCOUNTS)
    retirement = sum(by_account.get(a, 0.0) for a in RETIREMENT_ACCOUNTS)

    return {
        "total_value": round(total, 2),
        "holdings_count": len(holdings),
        "asset_allocations_pct": {k: _pct(v, total) for k, v in sorted(by_class.items(), key=lambda kv: -kv[1])},
        "sector_allocations_pct": {k: _pct(v, total) for k, v in sorted(by_sector.items(), key=lambda kv: -kv[1])},
        "account_allocations_pct": {k: _pct(v, total) for k, v in sorted(by_account.items(), key=lambda kv: -kv[1])},
        "position_pct": {k: _pct(v, total) for k, v in sorted(by_position.items(), key=lambda kv: -kv[1])},
        "top_position": {
            "ticker": top_ticker,
            "pct": _pct(non_cash.get(top_ticker, 0.0), total),
            "value": round(non_cash.get(top_ticker, 0.0), 2),
        },
        "largest_holding": {"ticker": largest, "pct": _pct(by_position[largest], total)},
        "max_sector_concentration_pct": max((_pct(v, total) for v in by_sector.values()), default=0.0),
        "pct_high_volatility": _pct(high_vol_value, total),
        "high_volatility_tickers": high_vol_tickers,
        "pct_equity": pct_equity,
        "pct_bond": pct_bond,
        "pct_cash": pct_cash,
        "pct_other": round(max(0.0, 100.0 - pct_equity - pct_bond - pct_cash), 2),
        "accessible_value": round(accessible, 2),
        "pct_accessible": _pct(accessible, total),
        "retirement_account_value": round(retirement, 2),
        # Unrounded values, used for rule comparisons so 30.001% isn't rounded down to a pass.
        "exact_pct": {
            "top_position": non_cash.get(top_ticker, 0.0) / total * 100,
            "high_volatility": high_vol_value / total * 100,
            "equity": sum(by_class[c] for c in EQUITY_CLASSES) / total * 100,
            "accessible": accessible / total * 100,
        },
        "age_allocations": {
            "actual_equity_pct": pct_equity, "target_equity_pct": targets["equity"],
            "actual_bond_pct": pct_bond, "target_bond_pct": targets["bond"],
            "actual_cash_pct": pct_cash, "target_cash_pct": targets["cash"],
            "equity_diff": round(pct_equity - targets["equity"], 2),
            "bond_diff": round(pct_bond - targets["bond"], 2),
            "cash_diff": round(pct_cash - targets["cash"], 2),
        },
    }


# --------------------------------------------------------------------------
# Market context
# --------------------------------------------------------------------------

def classify_market(vix: float, yield_10y: float, yield_3m: float) -> dict:
    vix_level = "elevated" if vix >= 20.0 else ("moderate" if vix >= 12.0 else "low")
    curve = "inverted_curve" if yield_3m > yield_10y else "normal_curve"
    return {"vix_level": vix_level, "rate_environment": curve}


def scenario_market_context(scenario: str) -> dict:
    preset = MARKET_SCENARIOS[scenario]
    ctx = {
        "vix": preset["vix"], "yield_10y": preset["yield_10y"], "yield_3m": preset["yield_3m"],
        "scenario": scenario, "scenario_label": preset["label"], "note": preset["note"],
        "source": "scenario_preset", "timestamp": utc_now(),
    }
    ctx.update(classify_market(ctx["vix"], ctx["yield_10y"], ctx["yield_3m"]))
    return ctx


def fetch_live_market_context(timeout: float = 5.0) -> dict:
    """Pull VIX and Treasury yields from Yahoo Finance; fall back to the baseline preset."""
    import urllib.request

    symbols = {"vix": "%5EVIX", "yield_10y": "%5ETNX", "yield_3m": "%5EIRX"}
    fetched: dict[str, float] = {}
    for key, sym in symbols.items():
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?interval=1d&range=1d"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                meta = json.loads(resp.read().decode())["chart"]["result"][0]["meta"]
                fetched[key] = float(meta["regularMarketPrice"])
        except Exception:
            break
    if len(fetched) != len(symbols):
        ctx = scenario_market_context("baseline")
        ctx["source"] = "cached_fallback"
        ctx["note"] = "Live quotes unavailable; using baseline values."
        return ctx
    ctx = {
        **{k: round(v, 3) for k, v in fetched.items()},
        "scenario": "live", "scenario_label": "Live (Yahoo Finance)",
        "note": "Live VIX and Treasury yields.", "source": "yahoo_finance_live",
        "timestamp": utc_now(),
    }
    ctx.update(classify_market(ctx["vix"], ctx["yield_10y"], ctx["yield_3m"]))
    return ctx


def utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


# --------------------------------------------------------------------------
# Financial stability
# --------------------------------------------------------------------------

def analyze_stability(profile: dict, market: dict | None = None) -> dict:
    income = max(float(profile.get("annual_income") or 0.0), 1.0)
    other_debt = float(profile.get("existing_other_debt") or 0.0)
    debt_to_income = other_debt / income
    stability = profile.get("income_stability", "unknown")
    employment = profile.get("employment_status", "unknown")
    credit = profile.get("credit_score_band", "unknown")

    deductions: list[tuple[str, int]] = []
    if stability == "variable":
        deductions.append(("Variable income", 15))
    elif stability not in ("stable",):
        deductions.append(("Income stability unknown", 5))
    if employment == "self_employed":
        deductions.append(("Self-employed", 10))
    elif employment == "business_owner":
        deductions.append(("Business owner", 8))
    elif employment == "unemployed":
        deductions.append(("Currently unemployed", 20))

    if debt_to_income > 0.30:
        deductions.append((f"Debt is {debt_to_income:.0%} of income", 20))
    elif debt_to_income > 0.15:
        deductions.append((f"Debt is {debt_to_income:.0%} of income", 10))
    elif debt_to_income > 0.05:
        deductions.append((f"Debt is {debt_to_income:.0%} of income", 5))

    credit_map = {
        "below_650": ("subprime", 25), "650_700": ("fair", 15),
        "700_750": ("good", 5), "750_plus": ("excellent", 0),
    }
    credit_standing, credit_pts = credit_map.get(credit, ("unknown", 10))
    if credit_pts:
        deductions.append((f"{credit_standing.title()} credit", credit_pts))

    score = max(0, 100 - sum(p for _, p in deductions))
    category = "High Stability" if score >= 80 else ("Moderate Stability" if score >= 60 else "Lower Stability")

    notes = []
    market = market or {}
    if other_debt > 5000 and float(market.get("yield_10y", 0.0)) > 4.0:
        notes.append(
            f"With 10-year Treasury yields at {market['yield_10y']}%, carrying "
            f"${other_debt:,.0f} of non-mortgage debt is expensive; paying it down "
            "is a guaranteed return."
        )

    return {
        "stability_score": score,
        "stability_category": category,
        "deductions": [{"reason": r, "points": p} for r, p in deductions],
        "credit_standing": credit_standing,
        "other_debt_to_income_pct": round(debt_to_income * 100, 2),
        "existing_other_debt": other_debt,
        "existing_mortgage_balance": float(profile.get("existing_mortgage_balance") or 0.0),
        "notes": notes,
    }


# --------------------------------------------------------------------------
# Risk tolerance check (advisory, separate from the hard compliance rules)
# --------------------------------------------------------------------------

RISK_BANDS = {
    "conservative": {"max_high_vol": 0.0, "max_equity": 60.0, "min_equity": 0.0},
    "moderate": {"max_high_vol": 30.0, "max_equity": 80.0, "min_equity": 30.0},
    "aggressive": {"max_high_vol": 100.0, "max_equity": 100.0, "min_equity": 40.0},
}


def _article(word: str) -> str:
    return "an" if word[:1].lower() in "aeiou" else "a"


def assess_risk(profile: dict, metrics: dict, market: dict | None = None) -> dict:
    tolerance = profile.get("stated_risk_tolerance", "moderate")
    band = RISK_BANDS.get(tolerance, RISK_BANDS["moderate"])
    hv, eq = metrics["pct_high_volatility"], metrics["pct_equity"]
    elevated = (market or {}).get("vix_level") == "elevated"
    findings = []

    if hv > band["max_high_vol"]:
        findings.append({
            "severity": "high" if elevated or tolerance == "conservative" else "medium",
            "message": f"{hv:.1f}% sits in high-volatility holdings; {_article(tolerance)} {tolerance} profile allows "
                       f"{band['max_high_vol']:.0f}%."
                       + (f" Market volatility is elevated (VIX {market['vix']})." if elevated else ""),
        })
    if eq > band["max_equity"]:
        findings.append({
            "severity": "medium",
            "message": f"Equity exposure of {eq:.1f}% is above the {band['max_equity']:.0f}% "
                       f"typical ceiling for {_article(tolerance)} {tolerance} investor.",
        })
    if eq < band["min_equity"]:
        findings.append({
            "severity": "low",
            "message": f"Only {eq:.1f}% is in stocks; {_article(tolerance)} {tolerance} investor usually holds at least "
                       f"{band['min_equity']:.0f}% to reach growth goals.",
        })

    actual_level = "low" if hv == 0 else ("moderate" if hv <= 30 else "high")
    return {
        "risk_tolerance_mismatch": bool(findings),
        "stated_risk": tolerance,
        "observed_risk": actual_level,
        "findings": findings,
        "mismatches": [f["message"] for f in findings],
        "market_context_factored": market is not None,
    }


# --------------------------------------------------------------------------
# Compliance rules R1–R6
# --------------------------------------------------------------------------

def evaluate_compliance(profile: dict, metrics: dict, rules: dict[str, dict] | None = None) -> dict:
    rules = rules or load_rules()
    p = {rid: r["params"] for rid, r in rules.items()}
    age = int(profile["age"])
    horizon = float(profile["time_horizon_years"])
    tolerance = profile.get("stated_risk_tolerance", "")
    liquidity = profile.get("liquidity_need", "")
    debt = float(profile.get("existing_other_debt") or 0.0)
    exact = metrics["exact_pct"]
    hv, hv_x = metrics["pct_high_volatility"], exact["high_volatility"]
    hv_list = ", ".join(metrics["high_volatility_tickers"]) or "none"
    top = metrics["top_position"]
    eq, eq_x = metrics["pct_equity"], exact["equity"]
    bench = metrics["age_allocations"]["target_equity_pct"]

    def record(rid: str, applies: bool, passed: bool, threshold: str, actual: str, details: str) -> dict:
        r = rules[rid]
        return {
            "rule_id": rid, "title": r["title"], "description": r["description"],
            "applies": applies, "passed": passed, "threshold": threshold, "actual": actual,
            "details": "" if passed else details, "why": r["why"],
            "resolvable_by_rebalance": r["resolvable_by_rebalance"],
        }

    out = []

    r1 = horizon <= p["R1"]["max_horizon_years"]
    ret = metrics["retirement_account_value"]
    out.append(record(
        "R1", r1, not (r1 and ret > 0),
        f"$0 in 401k/IRA when horizon ≤ {p['R1']['max_horizon_years']} yrs" if r1 else f"Applies only if horizon ≤ {p['R1']['max_horizon_years']} yrs",
        f"${ret:,.0f} in retirement accounts · {horizon:g}-yr horizon",
        f"${ret:,.0f} sits in 401k/IRA accounts against a {horizon:g}-year goal; early withdrawal would trigger penalties.",
    ))

    lim2 = p["R2"]["max_position_pct"]
    out.append(record(
        "R2", True, exact["top_position"] <= lim2, f"≤ {lim2:g}% in any one position",
        f"{top['ticker'] or '—'} = {top['pct']:.1f}%",
        f"{top['ticker']} makes up {top['pct']:.1f}% of the portfolio, above the {lim2:g}% limit.",
    ))

    r3 = tolerance == "conservative"
    lim3 = p["R3"]["max_high_vol_pct"]
    out.append(record(
        "R3", r3, not (r3 and hv_x > lim3),
        f"≤ {lim3:g}% high-volatility" if r3 else "Applies to conservative clients",
        f"{hv:.1f}% high-volatility ({hv_list})",
        f"Conservative client holds {hv:.1f}% in high-volatility holdings ({hv_list}); limit is {lim3:g}%.",
    ))

    r4 = liquidity == "high"
    lim4 = p["R4"]["min_accessible_pct"]
    acc = metrics["pct_accessible"]
    out.append(record(
        "R4", r4, not (r4 and exact["accessible"] < lim4),
        f"≥ {lim4:g}% in accessible accounts" if r4 else "Applies when liquidity need is high",
        f"{acc:.1f}% accessible",
        f"Liquidity need is high but only {acc:.1f}% is in savings, checking or taxable brokerage (minimum {lim4:g}%).",
    ))

    r5 = debt > p["R5"]["debt_threshold"]
    lim5 = p["R5"]["max_high_vol_pct"]
    out.append(record(
        "R5", r5, not (r5 and hv_x > lim5),
        f"≤ {lim5:g}% high-volatility" if r5 else f"Applies when other debt > ${p['R5']['debt_threshold']:,.0f}",
        f"{hv:.1f}% high-volatility · ${debt:,.0f} debt",
        f"Client carries ${debt:,.0f} of non-mortgage debt while holding {hv:.1f}% in high-volatility assets (limit {lim5:g}%).",
    ))

    r6 = age >= p["R6"]["min_age"]
    ceiling = bench + p["R6"]["buffer_pct"]
    out.append(record(
        "R6", r6, not (r6 and eq_x > ceiling),
        f"≤ {ceiling:g}% equity (benchmark {bench:g}% + {p['R6']['buffer_pct']:g})" if r6 else f"Applies from age {p['R6']['min_age']}",
        f"{eq:.1f}% equity",
        f"Equity is {eq:.1f}% versus a {ceiling:g}% ceiling for age {age} (benchmark {bench:g}%).",
    ))

    breaches = [
        {"rule_id": r["rule_id"], "description": r["description"], "details": r["details"]}
        for r in out if not r["passed"]
    ]
    return {
        "status": "PASS" if not breaches else "FLAG/REJECT",
        "rules": out,
        "breached_rules": breaches,
        "limits": {
            "max_single_ticker_pct": lim2,
            "high_volatility_limit_pct": min(
                [lim3] * r3 + [lim5] * r5, default=100.0),
            "accessible_pct_floor": lim4 if r4 else 0.0,
            "equity_max_benchmark_pct": ceiling if r6 else 100.0,
        },
        "timestamp": utc_now(),
    }


def health_score(breach_count: int) -> int:
    return max(0, 100 - POINTS_PER_BREACH * breach_count)


def priority_for(breached_ids: list[str]) -> str:
    if not breached_ids:
        return "Low"
    if len(breached_ids) >= 2 or any(r in CRITICAL_RULES for r in breached_ids):
        return "High"
    return "Medium"


# --------------------------------------------------------------------------
# Rebalancing
# --------------------------------------------------------------------------

def _sell_pro_rata(positions: list[dict], idxs: list[int], amount: float, reason: str, sells: dict) -> None:
    pool = sum(positions[i]["value"] for i in idxs)
    if pool <= 0 or amount <= 0:
        return
    amount = min(amount, pool)
    for i in idxs:
        cut = positions[i]["value"] / pool * amount
        if cut <= 0.005:
            continue
        positions[i]["value"] -= cut
        key = (positions[i]["account_type"], positions[i]["ticker"])
        sells[key]["amount"] += cut
        sells[key]["reasons"].add(reason)


def _bond_destination(positions: list[dict], sold: set[str]) -> str:
    totals = defaultdict(float)
    for pos in positions:
        totals[pos["ticker"]] += pos["value"]
    candidates = [t for t in BOND_DESTINATIONS if t not in sold] or list(BOND_DESTINATIONS)
    return min(candidates, key=lambda t: totals[t])


def propose_rebalance(profile: dict, holdings: list[dict], *, rules: dict | None = None,
                      norms: list[dict] | None = None, ticker_ref: dict | None = None,
                      max_passes: int = 4) -> dict:
    """Trim the positions behind each resolvable breach and reinvest inside the same account.

    Each pass re-audits the proposed portfolio, so the result reports whether the
    plan actually clears the rules rather than assuming it does. R1 and R4 depend
    on which *account* money sits in, which trades can't change without
    withdrawals, so they come back as advisor actions instead of trades.
    """
    rules = rules or load_rules()
    norms = norms or load_age_norms()
    ref = ticker_ref or load_ticker_reference()
    p = {rid: r["params"] for rid, r in rules.items()}
    age = int(profile["age"])
    positions = copy.deepcopy(holdings)
    sells: dict = defaultdict(lambda: {"amount": 0.0, "reasons": set()})
    buys: dict = defaultdict(lambda: {"amount": 0.0, "reasons": set()})
    before_metrics = compute_portfolio_metrics(holdings, age, norms)
    before = evaluate_compliance(profile, before_metrics, rules)
    passes = 0

    for _ in range(max_passes):
        metrics = compute_portfolio_metrics(positions, age, norms)
        audit = evaluate_compliance(profile, metrics, rules)
        failing = {r["rule_id"] for r in audit["rules"] if not r["passed"] and r["resolvable_by_rebalance"]}
        if not failing:
            break
        passes += 1
        total = metrics["total_value"]
        pass_sells: dict = defaultdict(lambda: {"amount": 0.0, "reasons": set()})

        if "R2" in failing:
            top = metrics["top_position"]["ticker"]
            excess = metrics["top_position"]["value"] - p["R2"]["rebalance_target_pct"] / 100 * total
            idxs = [i for i, h in enumerate(positions) if h["ticker"] == top]
            _sell_pro_rata(positions, idxs, excess, "R2", pass_sells)

        hv_targets = []
        if "R3" in failing:
            hv_targets.append(("R3", p["R3"]["rebalance_target_pct"]))
        if "R5" in failing:
            hv_targets.append(("R5", p["R5"]["rebalance_target_pct"]))
        if hv_targets:
            reason, target = min(hv_targets, key=lambda t: t[1])
            idxs = [i for i, h in enumerate(positions) if h["volatility"] == "high"]
            current = sum(positions[i]["value"] for i in idxs)
            _sell_pro_rata(positions, idxs, current - target / 100 * total, reason, pass_sells)
            for r, _t in hv_targets:
                for key in pass_sells:
                    if reason in pass_sells[key]["reasons"]:
                        pass_sells[key]["reasons"].add(r)

        if "R6" in failing:
            bench = metrics["age_allocations"]["target_equity_pct"]
            target = bench + p["R6"]["rebalance_buffer_pct"]
            eq_idx = [i for i, h in enumerate(positions) if h["asset_class"] in EQUITY_CLASSES]
            current = sum(positions[i]["value"] for i in eq_idx)
            excess = current - target / 100 * total
            # Sell the riskiest equity first, then single stocks, then funds.
            for tier in (
                [i for i in eq_idx if positions[i]["volatility"] == "high"],
                [i for i in eq_idx if positions[i]["asset_class"] == "equity" and positions[i]["volatility"] != "high"],
                [i for i in eq_idx if positions[i]["asset_class"] == "equity_fund"],
            ):
                if excess <= 0.5:
                    break
                tier_value = sum(positions[i]["value"] for i in tier)
                take = min(excess, tier_value)
                _sell_pro_rata(positions, tier, take, "R6", pass_sells)
                excess -= take

        # Reinvest each account's proceeds inside that same account.
        proceeds_by_account: dict[str, list] = defaultdict(lambda: [0.0, set(), set()])
        for (acct, ticker), s in pass_sells.items():
            proceeds_by_account[acct][0] += s["amount"]
            proceeds_by_account[acct][1] |= s["reasons"]
            proceeds_by_account[acct][2].add(ticker)
            sells[(acct, ticker)]["amount"] += s["amount"]
            sells[(acct, ticker)]["reasons"] |= s["reasons"]

        post = compute_portfolio_metrics(positions, age, norms)
        targets = post["age_allocations"]
        short_horizon = float(profile["time_horizon_years"]) <= 3 or profile.get("liquidity_need") == "high"
        for acct, (amount, reasons, sold_tickers) in proceeds_by_account.items():
            if amount <= 0.5:
                continue
            only_concentration = reasons == {"R2"}
            sold_equity = any(ref["tickers"].get(t, {}).get("asset_class") in EQUITY_CLASSES for t in sold_tickers)
            if only_concentration and sold_equity and post["pct_equity"] < targets["target_equity_pct"]:
                plan = [(EQUITY_DESTINATION, 1.0)]
            elif short_horizon:
                plan = [(CASH_DESTINATION, 1.0)]
            else:
                bond_share = targets["target_bond_pct"] / (targets["target_bond_pct"] + targets["target_cash_pct"])
                plan = [(_bond_destination(positions, sold_tickers), bond_share), (CASH_DESTINATION, 1 - bond_share)]
            for ticker, share in plan:
                amt = amount * share
                meta = ref["tickers"][ticker]
                existing = next((h for h in positions if h["ticker"] == ticker and h["account_type"] == acct), None)
                if existing:
                    existing["value"] += amt
                else:
                    positions.append({
                        "holding_id": "", "ticker": ticker, "asset_name": meta["asset_name"],
                        "account_type": acct, "shares": 0.0,
                        "price_per_share": ref["prices"].get(ticker, 1.0), "value": amt,
                        "asset_class": meta["asset_class"], "sector": meta["sector"],
                        "volatility": meta["volatility"],
                    })
                buys[(acct, ticker)]["amount"] += amt
                buys[(acct, ticker)]["reasons"] |= reasons

    positions = [h for h in positions if h["value"] > 0.5]
    for h in positions:
        h["value"] = round(h["value"], 2)
        if h["price_per_share"]:
            h["shares"] = round(h["value"] / h["price_per_share"], 4)
    after_metrics = compute_portfolio_metrics(positions, age, norms)
    after = evaluate_compliance(profile, after_metrics, rules)

    # Net out tickers that were both bought and sold in the same account across passes.
    net: dict = {}
    for key in set(sells) | set(buys):
        amount = buys[key]["amount"] - sells[key]["amount"]
        if abs(amount) >= 1.0:
            net[key] = (amount, sells[key]["reasons"] | buys[key]["reasons"])
    trades = []
    for (acct, ticker), (amount, reasons) in sorted(net.items(), key=lambda kv: (kv[1][0] > 0, -abs(kv[1][0]))):
        meta = ref["tickers"].get(ticker, {})
        price = ref["prices"].get(ticker)
        trades.append({
            "action": "BUY" if amount > 0 else "SELL",
            "ticker": ticker,
            "asset_name": meta.get("asset_name", ticker),
            "asset_class": meta.get("asset_class", "equity"),
            "account_type": acct,
            "amount": round(abs(amount), 2),
            "approx_shares": round(abs(amount) / price, 2) if price else None,
            "rules": sorted(reasons),
        })

    turnover = sum(t["amount"] for t in trades if t["action"] == "SELL")
    advisor_actions = []
    for r in after["rules"]:
        if r["passed"]:
            continue
        if r["rule_id"] == "R1":
            advisor_actions.append({
                "rule_id": "R1",
                "action": "Fund the near-term goal from taxable savings and new contributions; "
                          "leave the 401k/IRA invested for retirement rather than withdrawing early.",
            })
        elif r["rule_id"] == "R4":
            advisor_actions.append({
                "rule_id": "R4",
                "action": "Direct new savings into a high-yield savings or taxable brokerage account "
                          "until at least 25% of assets are reachable without penalty.",
            })
        else:
            advisor_actions.append({"rule_id": r["rule_id"], "action": "Manual review: automatic rebalance did not clear this rule."})

    return {
        "trades": trades,
        "turnover_value": round(turnover, 2),
        "turnover_pct": _pct(turnover, before_metrics["total_value"]),
        "passes": passes,
        "post_holdings": positions,
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "before_compliance": before,
        "after_compliance": after,
        "before_health_score": health_score(len(before["breached_rules"])),
        "after_health_score": health_score(len(after["breached_rules"])),
        "advisor_actions": advisor_actions,
        "fully_resolved": not after["breached_rules"],
    }


# --------------------------------------------------------------------------
# Planning strategy + advisor summary drafts
# --------------------------------------------------------------------------

ACCOUNT_LABELS = {
    "401k": "401(k)", "IRA": "IRA", "brokerage_taxable": "taxable brokerage account",
    "savings": "savings account", "checking": "checking account",
}

ACCOUNT_SHORT = {
    "401k": "401(k)", "IRA": "IRA", "brokerage_taxable": "Taxable brokerage",
    "savings": "Savings", "checking": "Checking",
}

GOAL_LABELS = {
    "retirement": "retirement", "home_purchase": "home purchase", "education": "education",
    "education_savings": "education", "wealth_growth": "long-term growth", "income": "retirement income",
    "capital_preservation": "capital preservation",
}


def build_strategy(profile: dict, stability: dict, metrics: dict, market: dict,
                   compliance: dict, plan: dict) -> dict:
    tolerance = profile.get("stated_risk_tolerance", "moderate")
    horizon = float(profile["time_horizon_years"])
    goal = profile.get("investment_goal", "")
    breached = [b["rule_id"] for b in compliance["breached_rules"]]
    directives = []

    if market.get("rate_environment") == "inverted_curve":
        directives.append("Yield curve inverted (3-month yield above 10-year): recession risk is elevated, so favour short-duration bonds and cash.")
    if market.get("vix_level") == "elevated":
        directives.append(f"Market volatility alert: VIX at {market['vix']}. Avoid adding to high-volatility equities.")
    if stability["stability_category"] == "Lower Stability":
        directives.append("Lower financial stability: keep a larger cash buffer before taking more market risk.")

    defensive = (
        tolerance == "conservative" or horizon <= 3 or profile.get("liquidity_need") == "high"
        or market.get("rate_environment") == "inverted_curve"
        or stability["stability_category"] == "Lower Stability"
    )
    if horizon <= 3 or (goal == "home_purchase" and horizon <= 5):
        stance, query = "capital preservation", "short-term treasury cash liquidity home down payment capital preservation"
    elif goal == "income" or (profile["age"] >= 60 and tolerance != "aggressive"):
        stance, query = "income", "dividend income retirees steady bond income inflation protected"
    elif defensive:
        stance, query = "defensive", "core fixed income bonds stability recession hedge"
    elif "R2" in breached and plan["trades"] and any(t["ticker"] == EQUITY_DESTINATION for t in plan["trades"]):
        stance, query = "diversify", "international diversification reduce single-position concentration diversified equity"
    elif tolerance == "aggressive":
        stance, query = "growth", "diversified equity growth global stocks"
    else:
        stance, query = "balanced", "core diversified equity growth and fixed income bonds"

    if breached:
        sells = sorted({t["ticker"] for t in plan["trades"] if t["action"] == "SELL"})
        rec = (
            f"{len(breached)} rule{'s' if len(breached) != 1 else ''} breached ({', '.join(breached)}). Take a {stance} stance: "
            + (f"trim {', '.join(sells)} " if sells else "")
            + f"and reinvest about ${plan['turnover_value']:,.0f} ({plan['turnover_pct']:.1f}% of assets) "
            "within the same accounts."
        )
    else:
        rec = f"Portfolio passes all rules. Maintain a {stance} stance aligned to the {GOAL_LABELS.get(goal, goal)} goal; no trades required."
    if plan["advisor_actions"]:
        rec += " Advisor follow-up needed for " + ", ".join(a["rule_id"] for a in plan["advisor_actions"]) + "."

    return {"stance": stance, "recommendation": rec, "directives": directives, "rag_query": query}


_LAYMAN = {
    "R1": "Money you'll need in {h:g} years is locked in retirement accounts that charge penalties for early withdrawal.",
    "R2": "Too much of your money ({pct:.0f}%) is in one investment ({ticker}); the limit is 30%.",
    "R3": "{hv:.0f}% of your money is in investments that swing a lot, which is too bumpy for a cautious investor.",
    "R4": "Only {acc:.0f}% of your money can be reached quickly without penalties; you said you may need cash soon.",
    "R5": "You owe ${debt:,.0f} on loans while {hv:.0f}% of your savings is in very bumpy investments.",
    "R6": "{eq:.0f}% of your money is in stocks, well above what's typical at age {age} ({bench:.0f}%).",
}


def draft_advisor_summary(state: dict) -> dict:
    profile = state["client_profile"]
    metrics = state["portfolio_metrics"]
    compliance = state["compliance_result"]
    market = state.get("market_context", {})
    stability = state.get("financial_stability_profile", {})
    plan = state.get("rebalance_plan") or {}
    rag = state.get("product_research_result") or {}
    breached = [b["rule_id"] for b in compliance["breached_rules"]]
    score = health_score(len(breached))
    name = str(profile.get("name", "Client")).split()[0]

    fmt = {
        "h": float(profile["time_horizon_years"]), "pct": metrics["top_position"]["pct"],
        "ticker": metrics["top_position"]["ticker"], "hv": metrics["pct_high_volatility"],
        "acc": metrics["pct_accessible"], "debt": float(profile.get("existing_other_debt") or 0.0),
        "eq": metrics["pct_equity"], "age": profile["age"],
        "bench": metrics["age_allocations"]["target_equity_pct"],
    }
    reasons = [_LAYMAN[r].format(**fmt) for r in breached]

    trades = plan.get("trades", [])
    sold = sorted({t["ticker"] for t in trades if t["action"] == "SELL"})
    if not breached:
        headline = f"✅ Approved: {name}'s portfolio fits a {profile['stated_risk_tolerance']} {GOAL_LABELS.get(profile['investment_goal'], 'investment')} plan."
        reasons.append("Every suitability rule that applies to this client passed.")
    elif trades:
        cleared = len(breached) - len(plan["after_compliance"]["breached_rules"])
        target = ("clear both rule breaches" if cleared == len(breached) == 2
                  else f"clear all {len(breached)} rule breaches" if cleared == len(breached) > 2
                  else "clear the rule breach" if cleared == len(breached)
                  else f"clear {cleared} of {len(breached)} rule breaches")
        headline = (f"⚠️ Rebalance: move ${plan['turnover_value']:,.0f} ({plan['turnover_pct']:.0f}%) "
                    f"out of {', '.join(sold)} to {target}.")
    else:
        headline = ("⚠️ Advisor review: this issue needs account-level changes, not trades." if len(breached) == 1
                    else f"⚠️ Advisor review: {len(breached)} issues need account-level changes, not trades.")

    if stability:
        level = stability["stability_category"].split()[0].lower()
        reasons.append(f"Financial stability is {level} ({stability['stability_score']}/100).")
    if market.get("vix_level") == "elevated":
        reasons.append(f"Markets are jumpy right now (VIX {market['vix']}), so we lean cautious.")
    if market.get("rate_environment") == "inverted_curve":
        reasons.append("Short-term rates are above long-term rates, an early recession warning.")

    safe_buys = sum(t["amount"] for t in trades if t["action"] == "BUY" and t["asset_class"] in BOND_CLASSES + CASH_CLASSES)
    income = 0.0
    if safe_buys and market.get("yield_3m"):
        income = round(safe_buys * float(market.get("yield_3m")) / 100, 0)
        reasons.append(f"Moving ${safe_buys:,.0f} into bonds and cash would earn roughly ${income:,.0f} a year at today's {market['yield_3m']}% short-term rate.")
    primary = rag.get("primary_match")
    if primary and breached:
        reasons.append(f"Suggested fund: {primary['ticker']} ({primary['name']}, {primary['expense_ratio']} yearly fee).")

    shifts = []
    for t in sorted(trades, key=lambda t: t["action"] != "SELL"):
        verb = "Sell" if t["action"] == "SELL" else "Buy"
        shifts.append(f"{verb} ${t['amount']:,.0f} of {t['ticker']} in the {ACCOUNT_LABELS.get(t['account_type'], t['account_type'])}")
    shifts += [f"{a['rule_id']}: {a['action']}" for a in plan.get("advisor_actions", [])]

    after = plan.get("after_health_score", score)
    if not breached:
        impact = "No changes needed; review again at the next annual check-in."
    elif plan.get("fully_resolved"):
        impact = f"Clears every breach and lifts the health score from {score} to {after}."
    else:
        impact = f"Lifts the health score from {score} to {after}; remaining items need advisor action."

    return {
        "headline": headline,
        "health_score": score,
        "priority": priority_for(breached),
        "status": compliance["status"],
        "reasons": reasons[:6],
        "shifts": shifts,
        "impact": impact,
        "estimated_annual_income": income,
        "checked_items": ["Risk alignment", "Liquidity", "Diversification", "Age suitability", "Debt exposure", "Goal horizon"],
    }


# Fields the LLM may not change: they are facts computed from the rules.
LOCKED_SUMMARY_FIELDS = ("health_score", "priority", "status", "estimated_annual_income", "checked_items")


def reconcile_summary(candidate: dict, draft: dict) -> tuple[dict, list[str]]:
    """Keep the model's wording but force computed fields back to the engine's values."""
    final = dict(draft)
    notes = []
    for key in ("headline", "impact"):
        if isinstance(candidate.get(key), str) and candidate[key].strip():
            final[key] = candidate[key].strip()
    for key in ("reasons", "shifts"):
        if isinstance(candidate.get(key), list) and all(isinstance(x, str) for x in candidate[key]) and candidate[key]:
            final[key] = candidate[key]
    for key in LOCKED_SUMMARY_FIELDS:
        if key in candidate and candidate[key] != draft[key]:
            notes.append(f"{key}: model said {candidate[key]!r}, engine computed {draft[key]!r}; kept engine value.")
    return final, notes


# --------------------------------------------------------------------------
# One-shot review without agents (client book triage, tests)
# --------------------------------------------------------------------------

def quick_review(profile: dict, holdings: list[dict], market: dict | None = None) -> dict:
    market = market or scenario_market_context("baseline")
    norms, rules, ref = load_age_norms(), load_rules(), load_ticker_reference()
    metrics = compute_portfolio_metrics(holdings, profile["age"], norms)
    compliance = evaluate_compliance(profile, metrics, rules)
    plan = propose_rebalance(profile, holdings, rules=rules, norms=norms, ticker_ref=ref)
    breached = [b["rule_id"] for b in compliance["breached_rules"]]
    return {
        "profile": profile, "metrics": metrics, "compliance": compliance, "plan": plan,
        "risk": assess_risk(profile, metrics, market),
        "stability": analyze_stability(profile, market),
        "health_score": health_score(len(breached)), "priority": priority_for(breached),
    }
