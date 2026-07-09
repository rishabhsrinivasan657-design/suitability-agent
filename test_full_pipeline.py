import asyncio
import pprint
import sys
import uuid
import re
import ast
import json
from typing import AsyncGenerator
from google.adk.runners import InMemoryRunner
from google.genai import types
from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_response import LlmResponse

class MockLlm(BaseLlm):
    model: str = "mock-model"
    
    async def generate_content_async(
        self, llm_request, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        sys_inst = llm_request.config.system_instruction or ""
        last_content = llm_request.contents[-1]
        
        # Check if this is a response to a tool call
        is_func_response = False
        func_name = ""
        func_response_val = ""
        for part in last_content.parts:
            if part.function_response:
                is_func_response = True
                func_name = part.function_response.name
                func_response_val = str(part.function_response.response)

        # 1. INTAKE AGENT
        if "Intake Agent" in sys_inst or "intake_agent" in sys_inst:
            if is_func_response:
                if func_name == "get_client":
                    try:
                        mcp_res = ast.literal_eval(func_response_val)
                        profile_json = mcp_res.get("structuredContent", {}).get("result", "")
                        if not profile_json:
                            profile_json = mcp_res.get("result", "")
                    except Exception:
                        profile_json = func_response_val
                        
                    yield LlmResponse(
                        content=types.Content(
                            role="model",
                            parts=[
                                types.Part(
                                    function_call=types.FunctionCall(
                                        name="save_client_profile",
                                        args={"profile_json": profile_json}
                                    )
                                )
                            ]
                        ),
                        partial=False
                    )
                elif func_name == "save_client_profile":
                    yield LlmResponse(
                        content=types.Content(
                            role="model",
                            parts=[types.Part(text="Intake completed and validated successfully.")]
                        ),
                        partial=False
                    )
            else:
                user_text = ""
                for part in last_content.parts:
                    if part.text:
                        user_text = part.text
                client_id = "C001" if "C001" in user_text else "C002"
                yield LlmResponse(
                    content=types.Content(
                        role="model",
                        parts=[
                            types.Part(
                                function_call=types.FunctionCall(
                                    name="get_client",
                                    args={"client_id": client_id}
                                )
                            )
                        ]
                    ),
                    partial=False
                )

        # 2. PERSONAL FINANCIAL ANALYST AGENT (New Agent 1)
        elif "Personal Financial Analyst Agent" in sys_inst or "personal_financial_analyst_agent" in sys_inst:
            if is_func_response:
                yield LlmResponse(
                    content=types.Content(
                        role="model",
                        parts=[types.Part(text="Financial stability profile created.")]
                    ),
                    partial=False
                )
            else:
                yield LlmResponse(
                    content=types.Content(
                        role="model",
                        parts=[
                            types.Part(
                                function_call=types.FunctionCall(
                                    name="analyze_financial_stability",
                                    args={}
                                )
                            )
                        ]
                    ),
                    partial=False
                )

        # 3. PORTFOLIO ANALYSIS AGENT
        elif "Portfolio Analysis Agent" in sys_inst or "portfolio_analysis_agent" in sys_inst:
            if is_func_response:
                yield LlmResponse(
                    content=types.Content(
                        role="model",
                        parts=[types.Part(text="Portfolio analysis step completed.")]
                    ),
                    partial=False
                )
            else:
                client_id = "C001" if "C001" in sys_inst else "C002"
                age = 34 if client_id == "C001" else 58
                yield LlmResponse(
                    content=types.Content(
                        role="model",
                        parts=[
                            types.Part(
                                function_call=types.FunctionCall(
                                    name="fetch_and_calculate_portfolio",
                                    args={"client_id": client_id, "age": age}
                                )
                            )
                        ]
                    ),
                    partial=False
                )

        # 4. MARKET SCOUT AGENT (New Agent 2)
        elif "Market Scout Agent" in sys_inst or "market_scout_agent" in sys_inst:
            if is_func_response:
                yield LlmResponse(
                    content=types.Content(
                        role="model",
                        parts=[types.Part(text="Market macro indicators fetched.")]
                    ),
                    partial=False
                )
            else:
                yield LlmResponse(
                    content=types.Content(
                        role="model",
                        parts=[
                            types.Part(
                                function_call=types.FunctionCall(
                                    name="fetch_market_context",
                                    args={}
                                )
                            )
                        ]
                    ),
                    partial=False
                )

        # 5. RISK ASSESSMENT AGENT
        elif "Risk Assessment Agent" in sys_inst or "risk_assessment_agent" in sys_inst:
            if is_func_response:
                yield LlmResponse(
                    content=types.Content(
                        role="model",
                        parts=[types.Part(text="Risk assessment step completed.")]
                    ),
                    partial=False
                )
            else:
                yield LlmResponse(
                    content=types.Content(
                        role="model",
                        parts=[
                            types.Part(
                                function_call=types.FunctionCall(
                                    name="assess_portfolio_risk",
                                    args={}
                                )
                            )
                        ]
                    ),
                    partial=False
                )

        # 6. COMPLIANCE AGENT
        elif "Compliance Agent" in sys_inst or "compliance_agent" in sys_inst:
            if is_func_response:
                yield LlmResponse(
                    content=types.Content(
                        role="model",
                        parts=[types.Part(text="Compliance audit step completed.")]
                    ),
                    partial=False
                )
            else:
                yield LlmResponse(
                    content=types.Content(
                        role="model",
                        parts=[
                            types.Part(
                                function_call=types.FunctionCall(
                                    name="evaluate_compliance_rules",
                                    args={}
                                )
                            )
                        ]
                    ),
                    partial=False
                )

        # 7. PLANNING/STRATEGY AGENT (New Agent 3)
        elif "Planning/Strategy Agent" in sys_inst or "planning_strategy_agent" in sys_inst:
            if is_func_response:
                yield LlmResponse(
                    content=types.Content(
                        role="model",
                        parts=[types.Part(text="Strategic rebalancing direction saved.")]
                    ),
                    partial=False
                )
            else:
                client_id = "C001" if "C001" in sys_inst else "C002"
                if client_id == "C001":
                    strat = {
                        "recommendation": "Because the client has high stability and stable horizon, suggest standard equity rebalancing to align single-position concentrations (VTI) within compliance caps."
                    }
                else:
                    strat = {
                        "recommendation": "Because the client has moderate stability but short-term home purchase goals and inverted market yields, recommend a defensive strategy shifting high-risk tech exposure to short-term bond safety floors."
                    }
                yield LlmResponse(
                    content=types.Content(
                        role="model",
                        parts=[
                            types.Part(
                                function_call=types.FunctionCall(
                                    name="save_planning_strategy",
                                    args={"strategy_json": json.dumps(strat)}
                                )
                            )
                        ]
                    ),
                    partial=False
                )

        # 8. PRODUCT RESEARCH AGENT (New RAG Component)
        elif "Product Research Agent" in sys_inst or "product_research_agent" in sys_inst:
            if is_func_response:
                yield LlmResponse(
                    content=types.Content(
                        role="model",
                        parts=[types.Part(text="RAG prospectus research completed.")]
                    ),
                    partial=False
                )
            else:
                yield LlmResponse(
                    content=types.Content(
                        role="model",
                        parts=[
                            types.Part(
                                function_call=types.FunctionCall(
                                    name="query_product_research",
                                    args={}
                                )
                            )
                        ]
                    ),
                    partial=False
                )

        # 9. ADVISOR SUMMARY AGENT
        elif "Advisor Summary Agent" in sys_inst or "advisor_summary_agent" in sys_inst:
            if is_func_response:
                yield LlmResponse(
                    content=types.Content(
                        role="model",
                        parts=[types.Part(text="Suitability process finished successfully.")]
                    ),
                    partial=False
                )
            else:
                client_id = "C001" if "C001" in sys_inst else "C002"
                
                if client_id == "C001":
                    memo_data = {
                        "headline": "⚠️ Rebalance: Reduce VTI concentration by 3.22% ($3,892) into cash/bonds",
                        "health_score": 85,
                        "priority": "Medium",
                        "reasons": [
                            "VTI concentration (33.22%) exceeds the 30% rule limit.",
                            "High stability profile supports long-term retirement goal.",
                            "BND (expense ratio 0.03%) is identified as a suitable reinvestment match."
                        ],
                        "shifts": [
                            "Reduce VTI concentration by 3.22% ($3,892)",
                            "Increase BND bond exposure by 3.22% ($3,892)"
                        ],
                        "impact": "Establishes single-position diversification compliance.",
                        "confidence": "98%",
                        "checked_items": ["Risk Alignment", "Liquidity", "Diversification", "Age Suitability"]
                    }
                else:
                    memo_data = {
                        "headline": "⚠️ Rebalance: Shift 37.1% ($71,700) from tech into short-term bond/cash safety floors",
                        "health_score": 55,
                        "priority": "High",
                        "reasons": [
                            "IRA retirement account holds VNQ with early-withdrawal risk.",
                            "Tech concentration (59.14%) exceeds conservative profile constraints.",
                            "CASH/BND total 4.84% vs 50% home-purchase goal requirement.",
                            "BND (Vanguard Total Bond Market ETF) selected via RAG query."
                        ],
                        "shifts": [
                            "Reduce NVDA/TSLA high volatility holdings by 44.16% ($85,420)",
                            "Shift IRA retirement VNQ holding to BND ($49,200)",
                            "Increase CASH/BND liquidity safety floor to 50% ($96,610)"
                        ],
                        "impact": "Mitigates technology sector over-concentration and secures liquid cash requirements.",
                        "confidence": "98%",
                        "checked_items": ["Risk Alignment", "Liquidity", "Diversification", "Age Suitability"]
                    }
                memo = json.dumps(memo_data)
                
                yield LlmResponse(
                    content=types.Content(
                        role="model",
                        parts=[
                            types.Part(
                                function_call=types.FunctionCall(
                                    name="save_final_summary",
                                    args={"summary_text": memo}
                                )
                            )
                        ]
                    ),
                    partial=False
                )

# Patch the models in our app
from app.agent import (
    app,
    intake_agent,
    personal_financial_analyst_agent,
    portfolio_analysis_agent,
    market_scout_agent,
    risk_assessment_agent,
    compliance_agent,
    planning_strategy_agent,
    product_research_agent,
    advisor_summary_agent
)

mock_llm = MockLlm()
intake_agent.model = mock_llm
personal_financial_analyst_agent.model = mock_llm
portfolio_analysis_agent.model = mock_llm
market_scout_agent.model = mock_llm
risk_assessment_agent.model = mock_llm
compliance_agent.model = mock_llm
planning_strategy_agent.model = mock_llm
product_research_agent.model = mock_llm
advisor_summary_agent.model = mock_llm

async def run_full_test(client_id: str):
    runner = InMemoryRunner(app=app)
    
    print("\n" + "="*60)
    print(f"--- EXECUTING WEALTH COMPLIANCE PIPELINE FOR CLIENT: {client_id} ---")
    print("="*60 + "\n")
    
    session_id = str(uuid.uuid4())
    # Create empty session
    session = await runner.session_service.create_session(
        app_name="app",
        user_id="test_user",
        session_id=session_id,
        state={}
    )
    
    msg = types.Content(
        role="user",
        parts=[types.Part(text=f"Run suitability analysis for client {client_id}.")]
    )
    
    # Run the pipeline
    async for event in runner.run_async(
        user_id="test_user",
        session_id=session.id,
        new_message=msg
    ):
        if event.content:
            if hasattr(event.content, "parts"):
                for part in event.content.parts:
                    if hasattr(part, "text") and part.text:
                        print(part.text, end="")
                    elif hasattr(part, "function_call") and part.function_call:
                        print(f"\n[Tool Call: {part.function_call.name}({part.function_call.args})]")
                    elif hasattr(part, "function_response") and part.function_response:
                        print(f"\n[Tool Response: {part.function_response.name} -> {part.function_response.response}]")
            elif isinstance(event.content, str):
                print(event.content, end="")
                
    # Reload session state and verify variables
    session = await runner.session_service.get_session(app_name="app", user_id="test_user", session_id=session.id)
    
    print("\n\n" + "-"*40)
    print("SESSION STATE VERIFICATION:")
    print("-"*40)
    
    keys = ["client_profile", "portfolio_metrics", "risk_flags", "compliance_result", "final_summary"]
    for key in keys:
        print(f"\nState Key '{key}':")
        pprint.pprint(session.state.get(key))

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_full_pipeline.py [C001|C002]")
        sys.exit(1)
        
    target_client = sys.argv[1].upper()
    asyncio.run(run_full_test(target_client))
