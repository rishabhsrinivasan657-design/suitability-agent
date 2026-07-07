import os
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

    Args:
        client_id: The client ID (e.g., C001) to fetch holdings for.
        age: The client's age (as an integer).
    """
    try:
        import sys
        sys.path.append("/Users/rishabhsrinivasan/Desktop/Projects/Kaggle")
        from mcp_server import get_holdings, get_age_allocation_norms
        
        holdings_json = get_holdings(client_id)
        norms_json = get_age_allocation_norms()
        
        holdings = json.loads(holdings_json)
        norms_data = json.loads(norms_json)
        
        total_value = sum(float(h["value"]) for h in holdings)
        if total_value == 0:
            return "Error: Portfolio total value is zero."

        asset_allocations = {}
        sector_allocations = {}
        total_illiquid = 0.0
        total_high_volatility = 0.0
        illiquid_assets = []

        for h in holdings:
            val = float(h["value"])
            ac = h["asset_class"].lower()
            asset_allocations[ac] = asset_allocations.get(ac, 0.0) + val

            sector = h["sector"].lower()
            if sector != "n/a":
                sector_allocations[sector] = sector_allocations.get(sector, 0.0) + val

            if h["liquidity"].lower() == "illiquid":
                total_illiquid += val
                illiquid_assets.append({
                    "ticker_or_asset": h["ticker_or_asset"],
                    "value": val,
                    "liquidity": h["liquidity"]
                })

            if h["volatility_rating"].lower() == "high":
                total_high_volatility += val

        asset_allocations_pct = {k: round((v / total_value) * 100, 2) for k, v in asset_allocations.items()}
        sector_allocations_pct = {k: round((v / total_value) * 100, 2) for k, v in sector_allocations.items()}
        
        pct_illiquid = round((total_illiquid / total_value) * 100, 2)
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

        actual_equity = asset_allocations_pct.get("equity", 0.0)
        actual_bond = asset_allocations_pct.get("bond", 0.0)
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
            "pct_illiquid": pct_illiquid,
            "pct_high_volatility": pct_high_volatility,
            "pct_alternative": asset_allocations_pct.get("alternative", 0.0),
            "pct_equity": actual_equity,
            "illiquid_assets": illiquid_assets,
            "age_allocations": age_allocations
        }

        tool_context.state["portfolio_metrics"] = portfolio_metrics
        return f"Success: Portfolio metrics successfully calculated and saved to state under key 'portfolio_metrics'."
    except Exception as e:
        return f"Error: Portfolio calculation failed: {str(e)}"


def assess_portfolio_risk(tool_context: ToolContext) -> str:
    """Analyzes client risk tolerance vs portfolio metrics and saves risk flags in 'risk_flags' state.
    """
    try:
        profile = tool_context.state.get("client_profile")
        metrics = tool_context.state.get("portfolio_metrics")
        
        if not profile or not metrics:
            return "Error: Missing client_profile or portfolio_metrics in state."
            
        risk_tolerance = profile.get("stated_risk_tolerance", "").lower()
        liquidity_need = profile.get("liquidity_need", "").lower()
        
        pct_high_volatility = metrics.get("pct_high_volatility", 0.0)
        pct_equity = metrics.get("pct_equity", 0.0)
        pct_illiquid = metrics.get("pct_illiquid", 0.0)
        
        mismatches = []
        
        # Volatility vs Stated Risk Tolerance check
        if risk_tolerance == "conservative":
            if pct_high_volatility > 0.0:
                mismatches.append(f"Stated risk tolerance is 'conservative' but portfolio has {pct_high_volatility}% in high volatility assets.")
            if pct_equity > 60.0:
                mismatches.append(f"Stated risk tolerance is 'conservative' but portfolio equity exposure is {pct_equity}% (exceeds 60% limit).")
        elif risk_tolerance == "moderate":
            if pct_high_volatility > 30.0:
                mismatches.append(f"Stated risk tolerance is 'moderate' but portfolio has {pct_high_volatility}% in high volatility assets (exceeds 30% limit).")
            if pct_equity > 80.0:
                mismatches.append(f"Stated risk tolerance is 'moderate' but portfolio equity exposure is {pct_equity}% (exceeds 80% limit).")
        elif risk_tolerance == "aggressive":
            if pct_equity < 40.0:
                mismatches.append(f"Stated risk tolerance is 'aggressive' but portfolio has only {pct_equity}% in equity (under-allocated for growth).")
        
        # Liquidity check
        if liquidity_need == "high" and pct_illiquid > 10.0:
            mismatches.append(f"Liquidity need is 'high' but portfolio contains {pct_illiquid}% in illiquid assets.")
        elif liquidity_need == "medium" and pct_illiquid > 20.0:
            mismatches.append(f"Liquidity need is 'medium' but portfolio contains {pct_illiquid}% in illiquid assets.")
            
        risk_flags = {
            "risk_tolerance_mismatch": len(mismatches) > 0,
            "mismatches": mismatches
        }
        
        tool_context.state["risk_flags"] = risk_flags
        return f"Success: Risk assessment completed. Found {len(mismatches)} mismatches. Saved to 'risk_flags'."
    except Exception as e:
        return f"Error: Risk assessment failed: {str(e)}"


def evaluate_compliance_rules(tool_context: ToolContext) -> str:
    """Evaluates portfolio compliance against suitability rules and saves result to state under 'compliance_result'.
    """
    try:
        profile = tool_context.state.get("client_profile")
        metrics = tool_context.state.get("portfolio_metrics")
        risk_flags = tool_context.state.get("risk_flags")
        
        if not profile or not metrics or not risk_flags:
            return "Error: Missing client_profile, portfolio_metrics, or risk_flags in state."
            
        import sys
        sys.path.append("/Users/rishabhsrinivasan/Desktop/Projects/Kaggle")
        from mcp_server import get_suitability_rules
        rules_json = get_suitability_rules()
        rules_data = json.loads(rules_json)
        
        breaches = []
        
        # Rule 1: Equity deviation must not exceed 20%
        age_alloc = metrics.get("age_allocations", {})
        equity_diff = age_alloc.get("equity_diff", 0.0)
        if abs(equity_diff) > 20.0:
            breaches.append({
                "rule_id": "R1",
                "description": "Equity deviation from age target must not exceed 20%.",
                "details": f"Actual equity deviation is {equity_diff}%."
            })
            
        # Determine dynamic illiquidity limit based on time horizon
        time_horizon = float(profile.get("time_horizon_years", 0))
        if time_horizon <= 3:
            illiquidity_limit = 5.0
        elif time_horizon <= 10:
            illiquidity_limit = 15.0
        else:
            illiquidity_limit = 25.0

        # Determine dynamic volatility limit based on risk tolerance
        risk_tolerance = profile.get("stated_risk_tolerance", "").lower()
        if risk_tolerance == "conservative":
            volatility_limit = 0.0
        elif risk_tolerance == "moderate":
            volatility_limit = 20.0
        else:
            volatility_limit = 50.0

        # Flat limits
        alternative_limit = 10.0
        sector_limit = 30.0

        # Rule 2: Max alternative asset concentration <= 10%
        pct_alt = metrics.get("pct_alternative", 0.0)
        if pct_alt > alternative_limit:
            breaches.append({
                "rule_id": "R2",
                "description": f"Max alternative asset concentration <= {alternative_limit}%.",
                "details": f"Actual alternative asset concentration is {pct_alt}%."
            })
            
        # Rule 3: Max illiquid asset concentration <= dynamic limit
        pct_illiquid = metrics.get("pct_illiquid", 0.0)
        if pct_illiquid > illiquidity_limit:
            breaches.append({
                "rule_id": "R3",
                "description": f"Max illiquid asset concentration <= {illiquidity_limit}%.",
                "details": f"Actual illiquid asset concentration is {pct_illiquid}%."
            })
            
        # Rule 4: Max sector concentration <= 30%
        max_sector = metrics.get("max_sector_concentration_pct", 0.0)
        if max_sector > sector_limit:
            breaches.append({
                "rule_id": "R4",
                "description": f"Max sector concentration <= {sector_limit}%.",
                "details": f"Actual max sector concentration is {max_sector}%."
            })
            
        # Rule 5: High volatility assets cannot exceed dynamic limit
        pct_high_vol = metrics.get("pct_high_volatility", 0.0)
        if pct_high_vol > volatility_limit:
            breaches.append({
                "rule_id": "R5",
                "description": f"High volatility assets cannot exceed {volatility_limit}% for {risk_tolerance} profile.",
                "details": f"Portfolio contains {pct_high_vol}% high volatility assets."
            })
            
        # Rule 6: If investment goal is home_purchase and time horizon <= 3 years, cash + short-term bonds >= 50%
        goal = profile.get("investment_goal", "").lower()
        horizon = float(profile.get("time_horizon_years", 999))
        if goal == "home_purchase" and horizon <= 3.0:
            actual_cash = metrics.get("asset_allocations_pct", {}).get("cash", 0.0)
            actual_bond = metrics.get("asset_allocations_pct", {}).get("bond", 0.0)
            cash_bond_total = actual_cash + actual_bond
            if cash_bond_total < 50.0:
                breaches.append({
                    "rule_id": "R6",
                    "description": "If investment goal is 'home_purchase' and time horizon <= 3 years, cash + short-term bonds must be >= 50% of the portfolio.",
                    "details": f"Actual cash + bonds is {cash_bond_total}%."
                })
        
        # Risk mismatches are also breaches
        mismatches = risk_flags.get("mismatches", [])
        for m in mismatches:
            breaches.append({
                "rule_id": "RISK_MISMATCH",
                "description": "Portfolio risk allocation does not align with client stated risk/liquidity profile.",
                "details": m
            })
            
        status = "PASS" if len(breaches) == 0 else "FLAG/REJECT"
        
        compliance_result = {
            "status": status,
            "limits": {
                "illiquidity_limit": illiquidity_limit,
                "volatility_limit": volatility_limit,
                "alternative_limit": alternative_limit,
                "sector_limit": sector_limit
            },
            "breached_rules": breaches,
            "timestamp": "2026-07-06T14:00:00Z"
        }
        
        tool_context.state["compliance_result"] = compliance_result
        return f"Success: Compliance evaluation completed. Status: {status}. Breaches found: {len(breaches)}. Saved to 'compliance_result'."
    except Exception as e:
        return f"Error: Compliance evaluation failed: {str(e)}"


def save_final_summary(summary_text: str, tool_context: ToolContext) -> str:
    """Saves the final investment recommendation summary to the session state under key 'final_summary'.

    Args:
        summary_text: The final summary content text.
    """
    tool_context.state["final_summary"] = summary_text
    return "Success: Final advisor summary saved to session state."

# Setup the MCP toolset for get_client
mcp_toolset = McpToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command="uv",
            args=["run", "python", "/Users/rishabhsrinivasan/Desktop/Projects/Kaggle/mcp_server.py"],
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
    instruction="""You are the Intake Agent for the wealth management compliance system.
Your goal is to fetch, validate, and store a client's profile in the session state.

Steps:
1. Identify the client_id (e.g. C001, C002) from the user's message.
2. Call the `get_client` tool with the client_id to fetch the client's profile.
3. Validate the retrieved client details. Ensure required fields are present:
   - name, age, annual_income, net_worth, investment_goal, time_horizon_years, stated_risk_tolerance, liquidity_need, dependents
4. Save the client profile into the session state by calling the `save_client_profile` tool with the exact JSON string.
5. End your turn by confirming the intake is successful.
""",
    tools=[mcp_toolset, save_client_profile],
)

# 2. Portfolio Analysis Agent
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

# 3. Risk Assessment Agent
risk_assessment_agent = Agent(
    name="risk_assessment_agent",
    model=Gemini(
        model="gemini-2.5-flash",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction="""You are the Risk Assessment Agent. Your job is to analyze risk tolerance vs actual portfolio metrics and flag mismatches.

Client profile from state:
{client_profile}

Portfolio metrics from state:
{portfolio_metrics}

Steps:
1. Call the `assess_portfolio_risk` tool to calculate and save the risk analysis in state.
2. End your turn.
""",
    tools=[assess_portfolio_risk],
)

# 4. Compliance Agent
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

# 5. Advisor Summary Agent
advisor_summary_agent = Agent(
    name="advisor_summary_agent",
    model=Gemini(
        model="gemini-2.5-flash",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction="""You are the Advisor Summary Agent. Your job is to generate a decisive, structured client suitability recommendation JSON.

State details:
Client profile: {client_profile}
Portfolio metrics: {portfolio_metrics}
Risk flags: {risk_flags}
Compliance result: {compliance_result}

Your output MUST be a valid JSON object matching this schema:
{
  "headline": "A bold, decisive one-line verdict indicating required shifts, e.g. '⚠️ Rebalance: Shift 37.1% ($115,000) from alternatives/illiquids into cash/bonds' or '✅ Portfolio Approved: Moderate growth asset mix is fully compliant'",
  "health_score": 85, // Integer from 0 to 100 based on compliance (e.g. 100 if PASS, subtract 15-20 per breach)
  "priority": "High", // "High" (if multiple critical rules fail), "Medium" (if minor dev), or "Low" (if PASS)
  "reasons": [
    "A list of 2-4 concise reasons using actual numbers from the client profile/portfolio, under 12 words per bullet."
  ],
  "shifts": [
    "A list of recommended asset-category changes showing concrete percentages/amounts, e.g., 'Reduce technology equity by 28.06% ($87,000)'"
  ],
  "impact": "A short sentence describing the expected business/compliance impact after rebalancing (under 15 words).",
  "confidence": "98%", // Recommendation confidence level based on rules engine alignment (usually 95%-99%)
  "checked_items": ["Risk Alignment", "Liquidity", "Diversification", "Age Suitability"]
}

Guidelines:
- Never recommend specific stock tickers or real-time timing. Suggest asset-category changes only.
- Compute the health_score: Start at 100, deduct 15 points per breached rule.
- If there are critical breaches (e.g. R3, R5, R6), set Priority to High.

Steps:
1. Review all the data in the state and formulate the JSON structure.
2. Call the `save_final_summary` tool with the serialized JSON string.
3. End your turn.
""",
    tools=[save_final_summary],
)

# --- Orchestration ---

# Loop portfolio analysis, risk assessment, and compliance check (1 iteration is sufficient)
analysis_compliance_loop = LoopAgent(
    name="analysis_compliance_loop",
    sub_agents=[portfolio_analysis_agent, risk_assessment_agent, compliance_agent],
    max_iterations=1,
)

# Sequential flow: Intake -> [Loop] -> Summary
root_agent = SequentialAgent(
    name="wealth_suitability_pipeline",
    sub_agents=[intake_agent, analysis_compliance_loop, advisor_summary_agent]
)

app = App(
    root_agent=root_agent,
    name="app",
)
