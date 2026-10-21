import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import engine  # noqa: E402


@pytest.fixture(scope="session")
def rules():
    return engine.load_rules()


@pytest.fixture(scope="session")
def norms():
    return engine.load_age_norms()


@pytest.fixture(scope="session")
def all_clients():
    return engine.load_all_clients()


def make_profile(**overrides) -> dict:
    base = {
        "client_id": "C9999", "name": "Test Client", "age": 40, "investment_goal": "retirement",
        "time_horizon_years": 20.0, "stated_risk_tolerance": "moderate", "liquidity_need": "medium",
        "employment_status": "employed", "income_stability": "stable", "annual_income": 100000.0,
        "existing_other_debt": 0.0, "existing_mortgage_balance": 0.0, "credit_score_band": "750_plus",
    }
    base.update(overrides)
    return base


def holding(ticker: str, value: float, account: str = "brokerage_taxable", **meta) -> dict:
    return {"ticker": ticker, "value": value, "account_type": account, **meta}


def portfolio(*items) -> list[dict]:
    return engine.enrich_holdings(list(items))
