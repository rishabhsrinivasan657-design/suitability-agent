import asyncio
import pprint
import sys
import uuid
import re
import ast
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
        if "Intake Agent" in sys_inst:
            if is_func_response:
                if func_name == "get_client":
                    # Parse the stringified python dict from MCP wrapper
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
                    # Final success response
                    yield LlmResponse(
                        content=types.Content(
                            role="model",
                            parts=[types.Part(text="Intake completed and validated successfully.")]
                        ),
                        partial=False
                    )
            else:
                # Find client id in prompt
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

        # 2. PORTFOLIO ANALYSIS AGENT
        elif "Portfolio Analysis Agent" in sys_inst:
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

        # 3. RISK ASSESSMENT AGENT
        elif "Risk Assessment Agent" in sys_inst:
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

        # 4. COMPLIANCE AGENT
        elif "Compliance Agent" in sys_inst:
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

        # 5. ADVISOR SUMMARY AGENT
        elif "Advisor Summary Agent" in sys_inst:
            if is_func_response:
                # print the saved final text
                yield LlmResponse(
                    content=types.Content(
                        role="model",
                        parts=[types.Part(text="Suitability process finished successfully.")]
                    ),
                    partial=False
                )
            else:
                # Yield a detailed recommendation memo based on the client
                client_name = "Priya Sharma" if "Priya Sharma" in sys_inst else "James Anderson"
                client_id = "C001" if "C001" in sys_inst else "C002"
                
                import json
                if client_id == "C001":
                    memo_data = {
                        "headline": "✅ Portfolio Approved: Moderate growth asset mix is fully compliant",
                        "health_score": 100,
                        "priority": "Low",
                        "confidence": "99%",
                        "reasons": [
                            "Current equity exposure (59.09%) is within target tolerance of age norm (75.0%).",
                            "Zero alternative or illiquid asset compliance breaches identified.",
                            "Volatile asset exposure aligns with stated moderate risk tolerance."
                        ],
                        "shifts": [],
                        "impact": "Maintain current allocation. Re-evaluate portfolio annually.",
                        "checked_items": ["Risk Alignment", "Liquidity", "Diversification", "Age Suitability"]
                    }
                else:
                    memo_data = {
                        "headline": "⚠️ Rebalance: Shift 37.1% ($115,000) from alternatives/illiquids into cash/bonds",
                        "health_score": 25,
                        "priority": "High",
                        "confidence": "98%",
                        "reasons": [
                            "Portfolio illiquidity (37.1%) exceeds your 5.0% short-horizon limit.",
                            "High-volatility holdings (72.58%) exceed your 0.0% conservative limit.",
                            "Sector concentration in technology (58.06%) exceeds 30.0% limit.",
                            "Cash + bonds total 4.84% vs 50.0% home_purchase goal requirement."
                        ],
                        "shifts": [
                            "Reduce high-volatility technology sector weight by 28.06% ($87,000)",
                            "Reduce alternative asset holdings by 4.52% ($14,000)",
                            "Increase cash and short-term bonds allocation by 45.16% ($140,000)"
                        ],
                        "impact": "Establishes compliant asset volatility and provides mandatory liquidity safety floor.",
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
    portfolio_analysis_agent,
    risk_assessment_agent,
    compliance_agent,
    advisor_summary_agent
)

mock_llm = MockLlm()
intake_agent.model = mock_llm
portfolio_analysis_agent.model = mock_llm
risk_assessment_agent.model = mock_llm
compliance_agent.model = mock_llm
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
                        print(f"\n[Tool Response: {part.function_response.name}]")
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
