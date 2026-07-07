import asyncio
import pprint
import sys
import uuid
from typing import AsyncGenerator
from google.adk.runners import InMemoryRunner
from google.genai import types
from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_response import LlmResponse

# Define MockLlm
class MockLlm(BaseLlm):
    model: str = "mock-model"
    
    async def generate_content_async(
        self, llm_request, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        last_content = llm_request.contents[-1]
        
        is_func_response = False
        func_name = ""
        for part in last_content.parts:
            if part.function_response:
                is_func_response = True
                func_name = part.function_response.name
                
        if is_func_response:
            # Response to tool call
            if func_name == "fetch_and_calculate_portfolio":
                summary = (
                    "Portfolio metrics successfully computed. "
                    "The client's actual allocations and age targets have been logged to the session state."
                )
                yield LlmResponse(
                    content=types.Content(
                        role="model",
                        parts=[types.Part(text=summary)]
                    ),
                    partial=False
                )
        else:
            # First turn: determine which client is target from user message
            user_text = ""
            for part in last_content.parts:
                if part.text:
                    user_text = part.text
            
            client_id = "C001"
            age = 34
            if "C002" in user_text:
                client_id = "C002"
                age = 58
                
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

# Import the app and patch the model
from app.agent import app, portfolio_analysis_agent
portfolio_analysis_agent.model = MockLlm()

async def run_test(client_id: str):
    runner = InMemoryRunner(app=app)
    
    # Define client profiles
    profiles = {
        "C001": {
            "client_id": "C001",
            "name": "Priya Sharma",
            "age": 34,
            "annual_income": 145000,
            "net_worth": 320000,
            "investment_goal": "retirement",
            "time_horizon_years": 25,
            "stated_risk_tolerance": "moderate",
            "liquidity_need": "medium",
            "dependents": 1
        },
        "C002": {
            "client_id": "C002",
            "name": "James Anderson",
            "age": 58,
            "annual_income": 95000,
            "net_worth": 410000,
            "investment_goal": "home_purchase",
            "time_horizon_years": 2,
            "stated_risk_tolerance": "conservative",
            "liquidity_need": "high",
            "dependents": 2
        }
    }
    
    if client_id not in profiles:
        print(f"Error: Unknown client ID '{client_id}'. Use 'C001' or 'C002'.")
        sys.exit(1)
        
    profile = profiles[client_id]
    print("========================================")
    print(f"--- TESTING CLIENT {client_id} ({profile['name']}) ---")
    print("========================================")
    
    session_id = str(uuid.uuid4())
    session = await runner.session_service.create_session(
        app_name="app",
        user_id="test_user",
        session_id=session_id,
        state={"client_profile": profile}
    )
    
    msg = types.Content(
        role="user",
        parts=[types.Part(text=f"Analyze the portfolio for client {client_id}.")]
    )
    
    # Run the agent
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
    
    # Reload session to check state
    session = await runner.session_service.get_session(app_name="app", user_id="test_user", session_id=session.id)
    print(f"\n\nFinal Portfolio Metrics saved in state ({client_id}):")
    pprint.pprint(session.state.get("portfolio_metrics"))

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_portfolio_standalone.py [C001|C002]")
        sys.exit(1)
        
    target_client = sys.argv[1].upper()
    asyncio.run(run_test(target_client))
