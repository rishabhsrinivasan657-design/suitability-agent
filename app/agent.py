import os
import sys
import json
from dotenv import load_dotenv

from google.adk.agents import Agent, SequentialAgent, LoopAgent
from google.adk.apps import App
from google.adk.models import Gemini
from google.genai import types
from google.adk.tools import ToolContext
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from mcp import StdioServerParameters

# Load environment variables
load_dotenv()
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "False"

# Portable base paths — works locally, in Docker, and on Railway
# This file lives at <project>/app/agent.py so BASE_DIR = <project>/
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
MCP_SERVER_PATH = os.path.join(BASE_DIR, "mcp_server.py")

# Make the project root importable (needed for mcp_server imports)
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# --- Tools ---

def save_client_profile(profile_json: str, tool_context: ToolContext) -> str:
    """Saves the validated client profile JSON structure to the session state.

    Args:
        profile_json: The validated client profile in JSON string format.
    """
    try:
        profile = json.loads(profile_json)
        tool_context.state["client_profile"] = profile
        return "Success: Client profile successfully saved to session state under key 'client_profile'."
    except Exception as e:
        return f"Error: Failed to parse and save client profile JSON: {str(e)}"


def fetch_and_calculate_portfolio(client_id: str, age: int, tool_context: ToolContext) -> str:
    """Fetches holdings and age norms, computes asset allocation and comparison benchmarks, and saves results in 'portfolio_metrics'.
    Maps tickers dynamically using the new ticker_reference.json metadata.
    """
    try:
        from mcp_server import get_holdings, get_age_allocation_norms, get_ticker_reference
        
        holdings_json = get_holdings(client_id)
        norms_json = get_age_allocation_norms()
        ticker_ref_json = get_ticker_reference()
        
        holdings = json.loads(holdings_json)
        norms_data = json.loads(norms_json)
        ticker_ref = json.loads(ticker_ref_json).get("tickers", {})
        
        total_value = sum(float(h["value"]) for h in holdings)
        if total_value == 0:
            return "Error: Portfolio total value is zero."

        asset_allocations = {}
        sector_allocations = {}
        total_high_volatility = 0.0
        high_vol_tickers = []
        
        for h in holdings:
            val = float(h["value"])
            ticker = h["ticker"]
            
            # Map ticker metadata
            ref = ticker_ref.get(ticker, {})
            ac = ref.get("asset_class", "cash").lower()
            sector = ref.get("sector", "n/a").lower()
            vol = ref.get("volatility", "none").lower()
            
            # Group actual allocations into standard brackets
            asset_allocations[ac] = asset_allocations.get(ac, 0.0) + val

            if sector != "n/a":
                sector_allocations[sector] = sector_allocations.get(sector, 0.0) + val

            if vol == "high":
                total_high_volatility += val
                high_vol_tickers.append(ticker)

        asset_allocations_pct = {k: round((v / total_value) * 100, 2) for k, v in asset_allocations.items()}
        sector_allocations_pct = {k: round((v / total_value) * 100, 2) for k, v in sector_allocations.items()}
        
        pct_high_volatility = round((total_high_volatility / total_value) * 100, 2)
        max_sector_concentration_pct = max(sector_allocations_pct.values()) if sector_allocations_pct else 0.0

        # Find norm bracket targets
        target_equity = 0.0
        target_bond = 0.0
        target_cash = 0.0
        for bracket in norms_data.get("brackets", []):
            if bracket["age_min"] <= age <= bracket["age_max"]:
                target_equity = bracket["target_equity_pct"]
                target_bond = bracket["target_bond_pct"]
                target_cash = bracket["target_cash_pct"]
                break

        # Define equity and bond sums (aggregating base assets and fund asset classes)
        actual_equity = asset_allocations_pct.get("equity", 0.0) + asset_allocations_pct.get("equity_fund", 0.0)
        actual_bond = asset_allocations_pct.get("bond_fund", 0.0) + asset_allocations_pct.get("bond", 0.0)
        actual_cash = asset_allocations_pct.get("cash", 0.0)
        
        age_allocations = {
            "actual_equity_pct": actual_equity,
            "target_equity_pct": target_equity,
            "actual_bond_pct": actual_bond,
            "target_bond_pct": target_bond,
            "actual_cash_pct": actual_cash,
            "target_cash_pct": target_cash,
            "equity_diff": round(actual_equity - target_equity, 2),
            "bond_diff": round(actual_bond - target_bond, 2),
            "cash_diff": round(actual_cash - target_cash, 2)
        }

        portfolio_metrics = {
            "total_value": total_value,
            "asset_allocations_pct": asset_allocations_pct,
            "sector_allocations_pct": sector_allocations_pct,
            "max_sector_concentration_pct": max_sector_concentration_pct,
            "pct_high_volatility": pct_high_volatility,
            "high_volatility_tickers": high_vol_tickers,
            "pct_equity": actual_equity,
            "pct_bond": actual_bond,
            "pct_cash": actual_cash,
            "age_allocations": age_allocations
        }

        tool_context.state["portfolio_metrics"] = portfolio_metrics
        return f"Success: Portfolio metrics successfully calculated and saved to state under key 'portfolio_metrics'."
    except Exception as e:
        return f"Error: Portfolio calculation failed: {str(e)}"


def analyze_financial_stability(tool_context: ToolContext) -> str:
    """Analyzes clients.csv fields (employment_status, income_stability, marital_status,
    existing_mortgage_balance, existing_other_debt, credit_score_band) from client_profile 
    and writes a structured financial_stability_profile to the session state under key 'financial_stability_profile'.
    """
    try:
        profile = tool_context.state.get("client_profile")
        if not profile:
            return "Error: Missing client_profile in session state."
            
        income_stability = profile.get("income_stability", "unknown").lower()
        employment_status = profile.get("employment_status", "unknown").lower()
        
        try:
            other_debt = float(profile.get("existing_other_debt", 0))
        except ValueError:
            other_debt = 0.0
            
        try:
            mortgage = float(profile.get("existing_mortgage_balance", 0))
        except ValueError:
            mortgage = 0.0
            
        try:
            annual_income = float(profile.get("annual_income", 1))
        except ValueError:
            annual_income = 1.0
            
        credit_band = profile.get("credit_score_band", "unknown").lower()
        
        # Calculate stability score (0-100)
        score = 100
        
        # Income stability deduction
        if income_stability == "variable":
            score -= 15
        elif income_stability == "unknown":
            score -= 5
            
        # Employment status deduction
        if employment_status == "self_employed":
            score -= 10
        elif employment_status == "business_owner":
            score -= 8
            
        # Debt ratio deductions
        debt_to_income = other_debt / annual_income
        if debt_to_income > 0.30:
            score -= 20
        elif debt_to_income > 0.15:
            score -= 10
        elif debt_to_income > 0.05:
            score -= 5
            
        # Credit score band deductions
        if credit_band == "below_650":
            score -= 25
            credit_standing = "subprime"
        elif credit_band == "650_700":
            score -= 15
            credit_standing = "fair"
        elif credit_band == "700_750":
            score -= 5
            credit_standing = "good"
        else:
            credit_standing = "excellent"
            
        # Stability Category
        if score >= 80:
            category = "High Stability"
            desc = f"Stable income, low debt ratio ({debt_to_income*100:.1f}%), and {credit_standing} credit standing."
        elif score >= 60:
            category = "Moderate Stability"
            desc = f"Muted debt profile, {credit_standing} credit standing, and {income_stability} income."
        else:
            category = "Lower Stability"
            desc = f"Elevated debt ratio ({debt_to_income*100:.1f}%), {credit_standing} credit standing, or variable income."
            
        # Change B: Dynamic rate-sensitive debt warning
        market = tool_context.state.get("market_context", {})
        yield_10y = market.get("yield_10y", 4.25)
        if other_debt > 5000.0 and yield_10y > 4.0:
            desc += f" Warning: High interest rate environment (10Y Yield: {yield_10y}%) makes carrying ${other_debt:,.0f} of non-mortgage debt very expensive. Prioritize paying off debt."
            
        stability_profile = {
            "stability_score": score,
            "stability_category": category,
            "qualitative_tags": desc,
            "credit_standing": credit_standing,
            "other_debt_to_income_pct": round(debt_to_income * 100, 2),
            "existing_other_debt": other_debt,
            "existing_mortgage_balance": mortgage
        }
        
        tool_context.state["financial_stability_profile"] = stability_profile
        return f"Success: Financial stability profile analyzed (Score: {score}/100, Category: {category}). Saved to state."
    except Exception as e:
        return f"Error: Financial stability analysis failed: {str(e)}"


def fetch_market_context(tool_context: ToolContext) -> str:
    """Fetches VIX, 10-Year Treasury Yield, and 3-Month Treasury Yield from Yahoo Finance.
    Falls back to cached realistic indicators if offline or network call fails.
    Saves market_context object to session state under key 'market_context'.
    """
    import urllib.request
    import json
    
    # Default/Cached Fallback Values
    results = {
        "vix": 14.5,
        "vix_level": "moderate", # low/moderate/elevated
        "yield_10y": 4.25,
        "yield_3m": 5.25,
        "rate_environment": "high/stable",
        "timestamp": "2026-07-08T22:00:00Z",
        "source": "cached_fallback"
    }
    
    # Try fetching real-time data from Yahoo Finance
    symbols = {
        "vix": "%5EVIX",
        "yield_10y": "%5ETNX",
        "yield_3m": "%5EIRX"
    }
    
    fetched = {}
    for name, sym in symbols.items():
        try:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?interval=1d&range=1d"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode('utf-8'))
                meta = data.get("chart", {}).get("result", [{}])[0].get("meta", {})
                price = meta.get("regularMarketPrice")
                if price is not None:
                    fetched[name] = float(price)
        except Exception:
            pass
            
    if len(fetched) == 3:
        results["vix"] = fetched["vix"]
        results["yield_10y"] = fetched["yield_10y"]
        results["yield_3m"] = fetched["yield_3m"]
        results["source"] = "yahoo_finance_live"
        
        # Determine VIX level
        if fetched["vix"] >= 20.0:
            results["vix_level"] = "elevated"
        elif fetched["vix"] >= 12.0:
            results["vix_level"] = "moderate"
        else:
            results["vix_level"] = "low"
            
        # Determine rate environment
        if fetched["yield_10y"] > fetched["yield_3m"]:
            results["rate_environment"] = "normal_curve"
        else:
            results["rate_environment"] = "inverted_curve"
            
    tool_context.state["market_context"] = results
    return f"Success: Market context fetched ({results['source']}). VIX: {results['vix']} ({results['vix_level']}), 10Y: {results['yield_10y']}%, 3M: {results['yield_3m']}%. Saved to state."


def assess_portfolio_risk(tool_context: ToolContext) -> str:
    """Analyzes client risk tolerance vs portfolio metrics and saves risk flags in 'risk_flags' state.
    Factors in real-time market context (elevated volatility).
    """
    try:
        profile = tool_context.state.get("client_profile")
        metrics = tool_context.state.get("portfolio_metrics")
        market = tool_context.state.get("market_context", {})
        
        if not profile or not metrics:
            return "Error: Missing client_profile or portfolio_metrics in state."
            
        risk_tolerance = profile.get("stated_risk_tolerance", "").lower()
        pct_high_volatility = metrics.get("pct_high_volatility", 0.0)
        pct_equity = metrics.get("pct_equity", 0.0)
        
        mismatches = []
        
        # Check if market volatility is elevated
        is_elevated_vol = market.get("vix_level") == "elevated"
        vix_val = market.get("vix", 14.5)
        
        # Volatility vs Stated Risk check
        if risk_tolerance == "conservative":
            if pct_high_volatility > 0.0:
                severity = "CRITICAL" if is_elevated_vol else "MODERATE"
                msg = f"Stated risk tolerance is 'conservative' but portfolio has {pct_high_volatility}% in high volatility assets."
                if is_elevated_vol:
                    msg += f" (HEAVY risk compounding due to elevated market volatility VIX={vix_val})"
                mismatches.append(msg)
            if pct_equity > 60.0:
                msg = f"Stated risk tolerance is 'conservative' but portfolio equity exposure is {pct_equity}% (exceeds 60% limit)."
                mismatches.append(msg)
        elif risk_tolerance == "moderate":
            if pct_high_volatility > 30.0:
                msg = f"Stated risk tolerance is 'moderate' but portfolio has {pct_high_volatility}% in high volatility assets (exceeds 30% limit)."
                if is_elevated_vol:
                    msg += f" (Warning: Market volatility VIX={vix_val} is elevated)"
                mismatches.append(msg)
            if pct_equity > 80.0:
                mismatches.append(f"Stated risk tolerance is 'moderate' but portfolio equity exposure is {pct_equity}% (exceeds 80% limit).")
        elif risk_tolerance == "aggressive":
            if pct_equity < 40.0:
                mismatches.append(f"Stated risk tolerance is 'aggressive' but portfolio has only {pct_equity}% in equity (under-allocated for growth).")
        
        risk_flags = {
            "risk_tolerance_mismatch": len(mismatches) > 0,
            "mismatches": mismatches,
            "market_context_factored": True
        }
        
        tool_context.state["risk_flags"] = risk_flags
        return f"Success: Risk assessment completed. Found {len(mismatches)} mismatches. Saved to 'risk_flags'."
    except Exception as e:
        return f"Error: Risk assessment failed: {str(e)}"


def evaluate_compliance_rules(tool_context: ToolContext) -> str:
    """Evaluates portfolio compliance against suitability rules R1–R6 from suitability_rules.json.
    Saves result to state under 'compliance_result'.
    """
    try:
        profile = tool_context.state.get("client_profile")
        metrics = tool_context.state.get("portfolio_metrics")
        
        if not profile or not metrics:
            return "Error: Missing client_profile or portfolio_metrics in state."
            
        from mcp_server import get_suitability_rules
        rules_json = get_suitability_rules()
        rules_data = json.loads(rules_json)
        
        breaches = []
        
        # Pull values
        age = int(profile.get("age", 0))
        time_horizon = float(profile.get("time_horizon_years", 999))
        risk_tolerance = profile.get("stated_risk_tolerance", "").lower()
        liquidity_need = profile.get("liquidity_need", "").lower()
        
        try:
            other_debt = float(profile.get("existing_other_debt", 0))
        except ValueError:
            other_debt = 0.0
            
        total_value = float(metrics.get("total_value", 1.0))
        
        # Calculate accessible values for R4
        from mcp_server import get_holdings
        client_id = profile.get("client_id")
        holdings = json.loads(get_holdings(client_id))
        
        acct_vals = {"savings": 0.0, "checking": 0.0, "brokerage_taxable": 0.0, "401k": 0.0, "IRA": 0.0}
        max_ticker_val = 0.0
        max_ticker = ""
        ticker_vals = {}
        
        for h in holdings:
            val = float(h["value"])
            acct = h["account_type"]
            acct_vals[acct] = acct_vals.get(acct, 0.0) + val
            
            ticker = h["ticker"]
            ticker_vals[ticker] = ticker_vals.get(ticker, 0.0) + val
            if ticker_vals[ticker] > max_ticker_val:
                max_ticker_val = ticker_vals[ticker]
                max_ticker = ticker
                
        accessible_sum = acct_vals.get("savings", 0.0) + acct_vals.get("checking", 0.0) + acct_vals.get("brokerage_taxable", 0.0)
        pct_accessible = (accessible_sum / total_value) * 100.0
        
        # Ticker concentration for R2
        pct_max_ticker = (max_ticker_val / total_value) * 100.0
        
        # High volatility tickers pct for R3 and R5
        pct_high_vol = float(metrics.get("pct_high_volatility", 0.0))
        high_vol_tickers_str = ", ".join(metrics.get("high_volatility_tickers", []))
        
        # Equity percentage and age norm for R6
        pct_equity = float(metrics.get("pct_equity", 0.0))
        age_alloc = metrics.get("age_allocations", {})
        age_norm_benchmark = float(age_alloc.get("target_equity_pct", 0.0))
        
        # Rule 1: Retirement account early-withdrawal risk vs. short time horizon
        retirement_sum = acct_vals.get("401k", 0.0) + acct_vals.get("IRA", 0.0)
        if time_horizon <= 3.0 and retirement_sum > 0.0:
            breaches.append({
                "rule_id": "R1",
                "description": "Retirement account early-withdrawal risk vs. short time horizon",
                "details": f"Retirement funds (401k/IRA) valued at ${retirement_sum:,.0f} held against a short-term {time_horizon:.0f}-year goal."
            })
            
        # Rule 2: Single-position concentration risk
        if (max_ticker_val / total_value) > 0.30:
            breaches.append({
                "rule_id": "R2",
                "description": "Single-position concentration risk",
                "details": f"Single-position concentration exceeds 30% of portfolio ({max_ticker} = {pct_max_ticker:.2f}%)"
            })
            
        # Rule 3: High-volatility exposure vs. conservative risk tolerance
        if risk_tolerance == "conservative" and (pct_high_vol / 100.0) > 0.15:
            breaches.append({
                "rule_id": "R3",
                "description": "High-volatility exposure vs. conservative risk tolerance",
                "details": f"Conservative client holds {pct_high_vol:.2f}% in high-volatility holdings ({high_vol_tickers_str})"
            })
            
        # Rule 4: Liquidity need vs. accessible account balance
        if liquidity_need == "high" and (accessible_sum / total_value) < 0.25:
            breaches.append({
                "rule_id": "R4",
                "description": "Liquidity need vs. accessible account balance",
                "details": f"High liquidity need but only {pct_accessible:.2f}% held in readily accessible accounts."
            })
            
        # Rule 5: Debt-adjusted risk exposure
        if other_debt > 20000.0 and (pct_high_vol / 100.0) > 0.20:
            breaches.append({
                "rule_id": "R5",
                "description": "Debt-adjusted risk exposure",
                "details": f"Client carries significant existing debt (${other_debt:,.0f}) while holding {pct_high_vol:.2f}% in high-volatility assets."
            })
            
        # Rule 6: Age-based equity allocation vs. benchmark
        if age >= 55 and pct_equity > (age_norm_benchmark + 15.0):
            breaches.append({
                "rule_id": "R6",
                "description": "Age-based equity allocation vs. benchmark",
                "details": f"Equity allocation ({pct_equity:.2f}%) significantly exceeds the typical benchmark for client's age bracket ({age_norm_benchmark}%)"
            })
            
        status = "PASS" if len(breaches) == 0 else "FLAG/REJECT"
        
        compliance_result = {
            "status": status,
            "breached_rules": breaches,
            "limits": {
                "max_single_ticker_pct": 30.0,
                "high_volatility_limit_pct": 15.0 if risk_tolerance == "conservative" else 50.0,
                "accessible_pct_floor": 25.0 if liquidity_need == "high" else 0.0,
                "equity_max_benchmark_pct": age_norm_benchmark + 15.0 if age >= 55 else 100.0
            },
            "timestamp": "2026-07-08T22:00:00Z"
        }
        
        tool_context.state["compliance_result"] = compliance_result
        return f"Success: Compliance evaluation completed. Status: {status}. Breaches found: {len(breaches)}. Saved to 'compliance_result'."
    except Exception as e:
        return f"Error: Compliance evaluation failed: {str(e)}"


def save_planning_strategy(strategy_json: str, tool_context: ToolContext) -> str:
    """Saves the planning strategy recommendation to the session state under key 'planning_strategy'."""
    try:
        strategy = json.loads(strategy_json)
        tool_context.state["planning_strategy"] = strategy
        return "Success: Planning strategy saved to session state under key 'planning_strategy'."
    except Exception:
        tool_context.state["planning_strategy"] = {"recommendation": strategy_json}
        return "Success: Planning strategy saved as raw recommendation."


def query_product_research(tool_context: ToolContext) -> str:
    """Loads the FAISS index, embeds the Planning/Strategy recommendation,
    finds the top relevant fund, and writes the RAG result to state under key 'product_research_result'.
    """
    try:
        strategy_data = tool_context.state.get("planning_strategy", {})
        query_text = strategy_data.get("recommendation", "")
        if not query_text:
            query_text = "Standard asset rebalancing for risk suitability"
            
        index_path = os.path.join(DATA_DIR, "faiss_index.bin")
        meta_path = os.path.join(DATA_DIR, "fund_metadata.json")
        
        if not os.path.exists(index_path) or not os.path.exists(meta_path):
            return "Error: FAISS index or metadata files do not exist. Please run setup_rag.py first."
            
        import faiss
        import numpy as np
        
        # Load FAISS index
        index = faiss.read_index(index_path)
        
        # Load metadata
        with open(meta_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)
            
        # Helper to generate query embedding
        from dotenv import load_dotenv
        load_dotenv()
        
        def get_query_embedding(text):
            import os
            if os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"):
                try:
                    from google import genai
                    client = genai.Client()
                    response = client.models.embed_content(
                        model="text-embedding-004",
                        contents=text
                    )
                    return response.embeddings[0].values
                except Exception:
                    pass
            
            # Smart Mock Fallback: pick seed based on keywords to match correct ticker
            t = text.lower()
            seed_ticker = "VTI"
            if "bond" in t or "fixed income" in t or "treasury" in t:
                seed_ticker = "BND"
            elif "real estate" in t or "reit" in t or "property" in t:
                seed_ticker = "VNQ"
            elif "cash" in t or "money market" in t or "liquidity" in t:
                seed_ticker = "VMFXX"
            elif "gold" in t or "alternative" in t:
                seed_ticker = "GLD"
            elif "dividend" in t:
                seed_ticker = "VYM"
            elif "technology" in t or "growth" in t or "nasdaq" in t:
                seed_ticker = "QQQ"
                
            np.random.seed(abs(hash(seed_ticker)) % (2**32))
            mock_vec = np.random.randn(768)
            mock_vec = mock_vec / np.linalg.norm(mock_vec)
            return mock_vec.tolist()
            
        query_vec = np.array([get_query_embedding(query_text)], dtype=np.float32)
        
        # Search index
        distances, indices = index.search(query_vec, k=2)
        
        matches = []
        for i in range(len(indices[0])):
            idx = int(indices[0][i])
            if 0 <= idx < len(metadata):
                fund = metadata[idx]
                matches.append(fund)
                
        res = {
            "query": query_text,
            "primary_match": matches[0] if len(matches) > 0 else None,
            "secondary_match": matches[1] if len(matches) > 1 else None,
            "timestamp": "2026-07-08T22:00:00Z"
        }
        
        tool_context.state["product_research_result"] = res
        return f"Success: Product research RAG completed. Selected primary fund: {res['primary_match']['ticker']} ({res['primary_match']['name']}). Saved to state."
    except Exception as e:
        return f"Error: Product research RAG failed: {str(e)}"


def save_final_summary(summary_text: str, tool_context: ToolContext) -> str:
    """Saves the final investment recommendation summary to the session state under key 'final_summary'.
    """
    tool_context.state["final_summary"] = summary_text
    return "Success: Final advisor summary saved to session state."

# Setup the MCP toolset for get_client
mcp_toolset = McpToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command="uv",
            args=["run", "python", MCP_SERVER_PATH],
        )
    ),
    tool_filter=["get_client"]
)

# --- Agents ---

# 1. Intake Agent
intake_agent = Agent(
    name="intake_agent",
    model=Gemini(
        model="gemini-2.5-flash",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction="""You are the Intake Agent.
Your goal is to fetch, validate, and store a client's profile in the session state.

Steps:
1. Identify the client_id (e.g. C001, C002) from the user's message.
2. Call the `get_client` tool with the client_id to fetch the client's profile.
3. Validate the retrieved client details. Ensure required fields are present.
4. Save the client profile into the session state by calling the `save_client_profile` tool with the exact JSON string.
5. End your turn by confirming the intake is successful.
""",
    tools=[mcp_toolset, save_client_profile],
)

# 2. Personal Financial Analyst Agent (New Agent 1)
personal_financial_analyst_agent = Agent(
    name="personal_financial_analyst_agent",
    model=Gemini(
        model="gemini-2.5-flash",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction="""You are the Personal Financial Analyst Agent.
Your job is to analyze the client's credit standing, marital/employment status, and debt level to build a financial stability profile.

Client profile from state:
{client_profile}

Steps:
1. Call the `analyze_financial_stability` tool to calculate stability scores and tags.
2. End your turn.
""",
    tools=[analyze_financial_stability],
)

# 3. Portfolio Analysis Agent
portfolio_analysis_agent = Agent(
    name="portfolio_analysis_agent",
    model=Gemini(
        model="gemini-2.5-flash",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction="""You are the Portfolio Analysis Agent. Your job is to calculate detailed asset allocations and compare them against age-based benchmarks.

Client profile from state:
{client_profile}

Steps you must perform:
1. Extract the client_id and age from the client_profile details above.
2. Call the `fetch_and_calculate_portfolio` tool, passing:
   - The client_id
   - The age (as an integer)
3. End your turn.
""",
    tools=[fetch_and_calculate_portfolio],
)

# 4. Market Scout Agent (New Agent 2)
market_scout_agent = Agent(
    name="market_scout_agent",
    model=Gemini(
        model="gemini-2.5-flash",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction="""You are the Market Scout Agent.
Your job is to gather recent macro interest rates and Volatility Index (VIX) trends.

Steps:
1. Call the `fetch_market_context` tool to retrieve interest rates and VIX levels.
2. End your turn.
""",
    tools=[fetch_market_context],
)

# 5. Risk Assessment Agent
risk_assessment_agent = Agent(
    name="risk_assessment_agent",
    model=Gemini(
        model="gemini-2.5-flash",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction="""You are the Risk Assessment Agent. Your job is to analyze risk tolerance vs actual portfolio metrics and flag mismatches, contextualizing the findings against current market conditions.

Client profile from state:
{client_profile}

Portfolio metrics from state:
{portfolio_metrics}

Market context from state:
{market_context}

Steps:
1. Call the `assess_portfolio_risk` tool to calculate and save the risk analysis in state.
2. End your turn.
""",
    tools=[assess_portfolio_risk],
)

# 6. Compliance Agent
compliance_agent = Agent(
    name="compliance_agent",
    model=Gemini(
        model="gemini-2.5-flash",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction="""You are the Compliance Agent. Your job is to check all suitability rules and flag compliance breaches.

Client profile from state:
{client_profile}

Portfolio metrics from state:
{portfolio_metrics}

Risk flags from state:
{risk_flags}

Steps:
1. Call the `evaluate_compliance_rules` tool to run and save the compliance check in state.
2. End your turn.
""",
    tools=[evaluate_compliance_rules],
)

# Loop portfolio analysis, risk assessment, and compliance check
analysis_compliance_loop = LoopAgent(
    name="analysis_compliance_loop",
    sub_agents=[
        portfolio_analysis_agent,
        risk_assessment_agent,
        compliance_agent
    ],
    max_iterations=1,
)

# 7. Planning/Strategy Agent (New Agent 3)
planning_strategy_agent = Agent(
    name="planning_strategy_agent",
    model=Gemini(
        model="gemini-2.5-flash",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction="""You are the Planning/Strategy Agent.
Your job is to formulate a specific, directional asset allocation strategy recommendation based on the client's stability profile, portfolio metrics, compliance status, and current market conditions.

State details:
Client profile: {client_profile}
Stability Profile: {financial_stability_profile}
Portfolio metrics: {portfolio_metrics}
Market context: {market_context}
Compliance result: {compliance_result}

Market Storm Check Guidelines:
- Look at `yield_3m` and `yield_10y` in the Market context. If `yield_3m` is higher than `yield_10y` (meaning the yield curve is inverted), explicitly mention: "Yield Curve Inverted (3M Yield > 10Y Yield): High recession risk detected. Activating defensive mode."
- Look at `vix` in the Market context. If `vix` is above 20.0, explicitly mention: "Market Volatility Alert: VIX is elevated. Recommend shifting away from risky equities."

Provide a concise strategy recommendation (e.g. "Because the client has lower stability and market VIX is elevated, reduce equity/bond risk exposure by shifting towards liquid capital safety floors").
Call the `save_planning_strategy` tool with your serialized JSON recommendation.
End your turn.
""",
    tools=[save_planning_strategy],
)

# 8. Product Research Agent (New RAG Component)
product_research_agent = Agent(
    name="product_research_agent",
    model=Gemini(
        model="gemini-2.5-flash",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction="""You are the Product Research Agent.
Your job is to query the local FAISS index for relevant fund prospectuses based on the Planning/Strategy recommendation.

Planning Strategy from state:
{planning_strategy}

Steps:
1. Call the `query_product_research` tool to perform the vector search and find matching funds.
2. End your turn.
""",
    tools=[query_product_research],
)

# 9. Advisor Summary Agent
advisor_summary_agent = Agent(
    name="advisor_summary_agent",
    model=Gemini(
        model="gemini-2.5-flash",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction="""You are the Advisor Summary Agent. Your job is to generate a decisive, structured client suitability recommendation JSON.

State details:
Client profile: {client_profile}
Financial Stability Profile: {financial_stability_profile}
Portfolio metrics: {portfolio_metrics}
Market context: {market_context}
Risk flags: {risk_flags}
Compliance result: {compliance_result}
Planning strategy: {planning_strategy}
Product research RAG results: {product_research_result}

Your output MUST be a valid JSON object matching this schema:
{{
  "headline": "A bold, decisive one-line verdict indicating required shifts, e.g. '⚠️ Rebalance: Shift 37.1% ($115,000) from alternatives/illiquids into cash/bonds' or '✅ Portfolio Approved: Moderate growth asset mix is fully compliant'",
  "health_score": 85, // Integer from 0 to 100 based on compliance (start at 100, deduct 15 points per breached rule)
  "priority": "High", // "High" (if multiple rules fail), "Medium" (if minor deviation), or "Low" (if PASS)
  "reasons": [
    "A list of 2-4 concise reasons using actual numbers, under 12 words per bullet. Make sure to reference real fund names/expense ratios from RAG, current market conditions, and stability factors!"
  ],
  "shifts": [
    "A list of recommended asset-category changes showing concrete percentages/amounts, e.g., 'Reduce technology equity by 28.06% ($87,000)'"
  ],
  "impact": "A short sentence describing the expected business/compliance impact after rebalancing (under 15 words).",
  "confidence": "98%", // Recommendation confidence level (usually 95%-99%)
  "checked_items": ["Risk Alignment", "Liquidity", "Diversification", "Age Suitability"]
}}

Guidelines:
- Layman Language Guideline: Write the headline, reasons, shifts, and impact in simple, jargon-free layman terms. For example, use 'too much money in one stock' instead of 'single-position concentration', 'safety buffer' instead of 'liquidity requirement', and 'steady earnings' instead of 'yield optimization'. Make sure the text is human-like and makes immediate sense to a retail client.
- Never recommend specific stock tickers or real-time timing. Suggest asset-category changes only (except for referencing matching funds from the RAG results).
- Compute the health_score: Start at 100, deduct 15 points per breached rule.
- If there are critical breaches (e.g. R3, R5, R6), set Priority to High.
- Estimate the exact annual interest income earned from the suggested shifts:
  - If rebalancing shifts some amount of money into bonds/cash, multiply that shift amount by the Treasury yield rate (using the 10Y yield from the Market context) and include the exact dollar earnings in the reasons list (e.g. "AGG matched. Reinvesting $3,892 at the current 10Y yield (4.569%) will generate $178 in annual income").

Steps:
1. Review all the data in the state and formulate the JSON structure.
2. Call the `save_final_summary` tool with the serialized JSON string.
3. End your turn.
""",
    tools=[save_final_summary],
)

# Sequential flow: Intake -> Market -> Stability -> [Loop: Portfolio -> Risk -> Compliance] -> Strategy -> RAG -> Summary
root_agent = SequentialAgent(
    name="wealth_suitability_pipeline",
    sub_agents=[
        intake_agent,
        market_scout_agent,
        personal_financial_analyst_agent,
        analysis_compliance_loop,
        planning_strategy_agent,
        product_research_agent,
        advisor_summary_agent
    ]
)

app = App(
    root_agent=root_agent,
    name="app",
)
