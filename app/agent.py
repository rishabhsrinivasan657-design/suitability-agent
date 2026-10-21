"""ShieldWealth: nine ADK agents that review a client portfolio for suitability.

Pipeline (SequentialAgent):
    1. intake_agent                    -> client_profile
    2. market_scout_agent              -> market_context
    3. personal_financial_analyst_agent-> financial_stability_profile
    4. portfolio_analysis_agent        -> portfolio_metrics, holdings
    5. risk_assessment_agent           -> risk_flags
    6. compliance_agent                -> compliance_result
    7. planning_strategy_agent         -> rebalance_plan, planning_strategy
    8. product_research_agent          -> product_research_result
    9. advisor_summary_agent           -> final_summary (+ summary_guardrail_notes)

Agents never pass data to each other directly: each reads and writes typed
session-state keys. All arithmetic lives in ``app.engine``; the LLM decides
which tool to call and writes the client-facing language, and
``save_final_summary`` forces computed fields (score, priority, status) back
to the engine's values so the model can't misstate them.
"""

from __future__ import annotations

import json
import os

from dotenv import load_dotenv
from google.adk.agents import Agent, SequentialAgent
from google.adk.apps import App
from google.adk.models import BaseLlm, Gemini
from google.adk.tools import ToolContext
from google.genai import types

from app import engine, rag

load_dotenv(os.path.join(engine.BASE_DIR, ".env"))

GEMINI_MODEL = os.environ.get("SHIELDWEALTH_MODEL", "gemini-2.5-flash")


# --------------------------------------------------------------------------
# Tools
# --------------------------------------------------------------------------

def get_client(client_id: str, tool_context: ToolContext) -> str:
    """Fetch the profile for one client_id (e.g. C001) from the client database via MCP.

    Args:
        client_id: The client identifier, "C" followed by digits.
    """
    staged = tool_context.state.get("staged_client")
    if staged and staged["profile"]["client_id"] == client_id.strip():
        return json.dumps(staged["profile"], ensure_ascii=False)
    try:
        return json.dumps(engine.load_client(client_id), ensure_ascii=False)
    except (KeyError, ValueError, FileNotFoundError) as e:
        return f"Error: {e}"


def save_client_profile(profile_json: str, tool_context: ToolContext) -> str:
    """Validate the client profile JSON and save it to session state as 'client_profile'.

    Args:
        profile_json: The client profile exactly as returned by get_client.
    """
    try:
        profile = engine.normalize_profile(json.loads(profile_json))
    except (json.JSONDecodeError, TypeError, ValueError) as e:
        return f"Error: profile is not valid JSON: {e}"
    missing = engine.missing_profile_fields(profile)
    if missing:
        return f"Error: profile is missing required fields: {', '.join(missing)}"
    tool_context.state["client_profile"] = profile
    return f"Success: saved profile for {profile['name']} ({profile['client_id']})."


def fetch_market_context(tool_context: ToolContext) -> str:
    """Fetch VIX and 3-month / 10-year Treasury yields and save them as 'market_context'.

    Uses the market scenario selected for this session; "live" pulls Yahoo Finance
    and falls back to cached baseline values when offline.
    """
    scenario = tool_context.state.get("market_scenario", "baseline")
    ctx = engine.fetch_live_market_context() if scenario == "live" else engine.scenario_market_context(scenario)
    tool_context.state["market_context"] = ctx
    return (f"Success: {ctx['scenario_label']} — VIX {ctx['vix']} ({ctx['vix_level']}), "
            f"10Y {ctx['yield_10y']}%, 3M {ctx['yield_3m']}% ({ctx['rate_environment']}).")


def analyze_financial_stability(tool_context: ToolContext) -> str:
    """Score the client's income stability, debt load and credit standing; saves 'financial_stability_profile'."""
    profile = tool_context.state.get("client_profile")
    if not profile:
        return "Error: client_profile missing from state."
    result = engine.analyze_stability(profile, tool_context.state.get("market_context"))
    tool_context.state["financial_stability_profile"] = result
    return f"Success: stability {result['stability_score']}/100 ({result['stability_category']})."


def fetch_and_calculate_portfolio(tool_context: ToolContext) -> str:
    """Load the client's holdings and compute allocations vs. age benchmarks; saves 'portfolio_metrics'."""
    profile = tool_context.state.get("client_profile")
    if not profile:
        return "Error: client_profile missing from state."
    staged = tool_context.state.get("staged_client")
    if staged and staged["profile"]["client_id"] == profile["client_id"]:
        holdings = engine.enrich_holdings(staged["holdings"])
    else:
        holdings = engine.load_holdings(profile["client_id"])
    if not holdings:
        return f"Error: no holdings on file for {profile['client_id']}."
    metrics = engine.compute_portfolio_metrics(holdings, profile["age"])
    tool_context.state["holdings"] = holdings
    tool_context.state["portfolio_metrics"] = metrics
    return (f"Success: {metrics['holdings_count']} holdings worth ${metrics['total_value']:,.0f}; "
            f"equity {metrics['pct_equity']}% vs target {metrics['age_allocations']['target_equity_pct']}%.")


def assess_portfolio_risk(tool_context: ToolContext) -> str:
    """Compare stated risk tolerance with the portfolio's actual risk in today's market; saves 'risk_flags'."""
    profile, metrics = tool_context.state.get("client_profile"), tool_context.state.get("portfolio_metrics")
    if not profile or not metrics:
        return "Error: client_profile or portfolio_metrics missing from state."
    flags = engine.assess_risk(profile, metrics, tool_context.state.get("market_context"))
    tool_context.state["risk_flags"] = flags
    return f"Success: {len(flags['findings'])} risk finding(s)."


def evaluate_compliance_rules(tool_context: ToolContext) -> str:
    """Audit the portfolio against suitability rules R1–R6; saves 'compliance_result'."""
    profile, metrics = tool_context.state.get("client_profile"), tool_context.state.get("portfolio_metrics")
    if not profile or not metrics:
        return "Error: client_profile or portfolio_metrics missing from state."
    result = engine.evaluate_compliance(profile, metrics)
    tool_context.state["compliance_result"] = result
    ids = [b["rule_id"] for b in result["breached_rules"]]
    return f"Success: status {result['status']}; breached: {', '.join(ids) or 'none'}."


def get_strategy_baseline(tool_context: ToolContext) -> str:
    """Build a rebalancing plan that is re-audited against R1–R6, plus a baseline strategy recommendation.

    Saves the plan as 'rebalance_plan' and returns the baseline strategy JSON
    (stance, recommendation, directives, rag_query) for you to refine and save.
    """
    s = tool_context.state
    needed = ("client_profile", "portfolio_metrics", "compliance_result", "holdings")
    if any(k not in s for k in needed):
        return "Error: earlier analysis steps are missing from state."
    plan = engine.propose_rebalance(s["client_profile"], s["holdings"])
    s["rebalance_plan"] = plan
    strategy = engine.build_strategy(
        s["client_profile"], s.get("financial_stability_profile", {}), s["portfolio_metrics"],
        s.get("market_context", {}), s["compliance_result"], plan,
    )
    return json.dumps(strategy, ensure_ascii=False)


def save_planning_strategy(strategy_json: str, tool_context: ToolContext) -> str:
    """Save the planning strategy (JSON with stance, recommendation, directives, rag_query) as 'planning_strategy'.

    Args:
        strategy_json: The strategy JSON object.
    """
    try:
        strategy = json.loads(strategy_json)
        if not isinstance(strategy, dict) or not strategy.get("recommendation"):
            raise ValueError("needs a 'recommendation' field")
    except (json.JSONDecodeError, ValueError):
        strategy = {"recommendation": str(strategy_json), "stance": "unspecified", "directives": [], "rag_query": str(strategy_json)}
    tool_context.state["planning_strategy"] = strategy
    return "Success: planning strategy saved."


def query_product_research(tool_context: ToolContext) -> str:
    """Search the fund prospectus index (FAISS) for funds matching the strategy and the client's risk profile.

    Saves 'product_research_result'.
    """
    strategy = tool_context.state.get("planning_strategy") or {}
    profile = tool_context.state.get("client_profile") or {}
    query = strategy.get("rag_query") or strategy.get("recommendation") or "diversified core portfolio"
    try:
        matches = rag.search(query, risk_tolerance=profile.get("stated_risk_tolerance"), k=3)
    except (FileNotFoundError, RuntimeError) as e:
        return f"Error: {e}"
    tool_context.state["product_research_result"] = {
        "query": query,
        "matches": matches,
        "primary_match": matches[0] if matches else None,
        "secondary_match": matches[1] if len(matches) > 1 else None,
        "corpus_size": rag.corpus_size(),
    }
    return "Success: matched " + ", ".join(f"{m['ticker']} ({m['score']:.2f})" for m in matches) + "."


def draft_advisor_summary(tool_context: ToolContext) -> str:
    """Return a draft client summary JSON computed from all session state, for you to polish and save."""
    s = tool_context.state
    try:
        return json.dumps(engine.draft_advisor_summary(s.to_dict() if hasattr(s, "to_dict") else dict(s)), ensure_ascii=False)
    except KeyError as e:
        return f"Error: missing state key {e}"


def save_final_summary(summary_text: str, tool_context: ToolContext) -> str:
    """Save the final client summary JSON as 'final_summary'.

    Computed fields (health_score, priority, status, estimated_annual_income,
    checked_items) are checked against the rules engine and corrected if they differ.

    Args:
        summary_text: The summary JSON object.
    """
    s = tool_context.state
    draft = engine.draft_advisor_summary(s.to_dict() if hasattr(s, "to_dict") else dict(s))
    try:
        candidate = json.loads(summary_text.strip().removeprefix("```json").removesuffix("```"))
        if not isinstance(candidate, dict):
            raise ValueError
    except (json.JSONDecodeError, ValueError):
        s["final_summary"] = draft
        s["summary_guardrail_notes"] = ["Model output was not valid JSON; used the engine draft."]
        return "Saved engine draft (model output was not valid JSON)."
    final, notes = engine.reconcile_summary(candidate, draft)
    s["final_summary"] = final
    s["summary_guardrail_notes"] = notes
    return "Success: final summary saved." + (f" Guardrail corrected {len(notes)} field(s)." if notes else "")


# --------------------------------------------------------------------------
# Agents
# --------------------------------------------------------------------------

AGENT_SPECS: list[dict] = [
    {
        "name": "intake_agent",
        "title": "Intake",
        "tools": [get_client, save_client_profile],
        "instruction": """You are the Intake Agent.
1. Find the client_id (e.g. C001) in the user's message.
2. Call `get_client` with it.
3. Call `save_client_profile` with the exact JSON that get_client returned.
If either tool returns an error, stop and report it.""",
    },
    {
        "name": "market_scout_agent",
        "title": "Market Scout",
        "tools": [fetch_market_context],
        "instruction": "You are the Market Scout Agent. Call `fetch_market_context` once, then summarise the result in one sentence.",
    },
    {
        "name": "personal_financial_analyst_agent",
        "title": "Financial Analyst",
        "tools": [analyze_financial_stability],
        "instruction": "You are the Personal Financial Analyst Agent. Call `analyze_financial_stability` once, then summarise the score in one sentence.",
    },
    {
        "name": "portfolio_analysis_agent",
        "title": "Portfolio Analysis",
        "tools": [fetch_and_calculate_portfolio],
        "instruction": "You are the Portfolio Analysis Agent. Call `fetch_and_calculate_portfolio` once, then summarise the allocation in one sentence.",
    },
    {
        "name": "risk_assessment_agent",
        "title": "Risk Assessment",
        "tools": [assess_portfolio_risk],
        "instruction": "You are the Risk Assessment Agent. Call `assess_portfolio_risk` once, then summarise the findings in one sentence.",
    },
    {
        "name": "compliance_agent",
        "title": "Compliance",
        "tools": [evaluate_compliance_rules],
        "instruction": "You are the Compliance Agent. Call `evaluate_compliance_rules` once, then state the status and any breached rule IDs.",
    },
    {
        "name": "planning_strategy_agent",
        "title": "Planning & Strategy",
        "tools": [get_strategy_baseline, save_planning_strategy],
        "instruction": """You are the Planning/Strategy Agent.
1. Call `get_strategy_baseline`. It builds a rebalancing plan that has already been re-audited against the rules and returns a baseline strategy JSON.
2. Review it against the client and market context below. You may sharpen the wording of `recommendation` and `directives`, but keep `stance` and `rag_query` unless they clearly contradict the context.
3. Call `save_planning_strategy` with the final JSON object.

Client: {client_profile?}
Stability: {financial_stability_profile?}
Market: {market_context?}
Compliance status: {compliance_result?}""",
    },
    {
        "name": "product_research_agent",
        "title": "Product Research (RAG)",
        "tools": [query_product_research],
        "instruction": "You are the Product Research Agent. Call `query_product_research` once, then name the top match in one sentence.",
    },
    {
        "name": "advisor_summary_agent",
        "title": "Advisor Summary",
        "tools": [draft_advisor_summary, save_final_summary],
        "instruction": """You are the Advisor Summary Agent. You write the client-facing verdict.
1. Call `draft_advisor_summary` to get a draft JSON computed from the analysis.
2. Rewrite `headline`, `reasons`, `shifts` and `impact` in plain, friendly language a retail client understands
   (say "too much money in one stock", not "single-position concentration"). Keep every number exactly as in the draft.
   Never invent tickers, percentages or dollar amounts. Do not change health_score, priority, status,
   estimated_annual_income or checked_items.
3. Call `save_final_summary` with the full JSON object.""",
    },
]

AGENT_TITLES = {spec["name"]: spec["title"] for spec in AGENT_SPECS}


def default_model() -> Gemini:
    return Gemini(model=GEMINI_MODEL, retry_options=types.HttpRetryOptions(attempts=3))


def build_pipeline(model: BaseLlm | None = None) -> SequentialAgent:
    """Build a fresh agent tree. Each run gets its own tree so concurrent sessions never share agents."""
    model = model or default_model()
    agents = {spec["name"]: Agent(name=spec["name"], model=model, instruction=spec["instruction"], tools=spec["tools"])
              for spec in AGENT_SPECS}
    review_stage = SequentialAgent(
        name="portfolio_review_stage",
        sub_agents=[agents["portfolio_analysis_agent"], agents["risk_assessment_agent"], agents["compliance_agent"]],
    )
    return SequentialAgent(
        name="wealth_suitability_pipeline",
        sub_agents=[
            agents["intake_agent"],
            agents["market_scout_agent"],
            agents["personal_financial_analyst_agent"],
            review_stage,
            agents["planning_strategy_agent"],
            agents["product_research_agent"],
            agents["advisor_summary_agent"],
        ],
    )


root_agent = build_pipeline()

app = App(root_agent=root_agent, name="app")
