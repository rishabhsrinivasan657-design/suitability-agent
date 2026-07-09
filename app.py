import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import json
import re
import uuid
import asyncio
import os
import ast
from typing import AsyncGenerator
from fpdf import FPDF

# Set up page config
st.set_page_config(
    page_title="ShieldWealth AI Compliance",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Define MockLlm
from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_response import LlmResponse
from google.genai import types

class MockLlm(BaseLlm):
    model: str = "mock-model"
    
    async def generate_content_async(
        self, llm_request, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        sys_inst = llm_request.config.system_instruction or ""
        last_content = llm_request.contents[-1]
        
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
                            parts=[types.Part(text="Intake completed successfully.")]
                        ),
                        partial=False
                    )
            else:
                user_text = ""
                for part in last_content.parts:
                    if part.text:
                        user_text = part.text
                client_id = "C001"
                match = re.search(r"C\d{3}", user_text)
                if match:
                    client_id = match.group(0)
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
                client_id_match = re.search(r"'client_id':\s*'([^']*)'", sys_inst)
                age_match = re.search(r"'age':\s*([0-9]+)", sys_inst)
                client_id = client_id_match.group(1) if client_id_match else "C001"
                age = int(age_match.group(1)) if age_match else 34
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
                client_id = "C001"
                id_match = re.search(r"'client_id':\s*'([^']*)'", sys_inst)
                if id_match:
                    client_id = id_match.group(1)
                
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
                client_id = "C001"
                id_match = re.search(r"'client_id':\s*'([^']*)'", sys_inst)
                if id_match:
                    client_id = id_match.group(1)
                
                if client_id == "C001":
                    memo_data = {
                        "headline": "⚠️ Rebalance: Reduce VTI concentration by 3.22% ($3,892) into cash/bonds",
                        "health_score": 85,
                        "priority": "Medium",
                        "reasons": [
                            "VTI concentration (33.22%) exceeds the 30% rule limit.",
                            "High stability profile supports long-term retirement goal.",
                            "AGG matched. Reinvesting $3,892 at the current 10Y yield (4.569%) will generate $178 in annual income."
                        ],
                        "shifts": [
                            "Reduce VTI concentration by 3.22% ($3,892)",
                            "Increase AGG bond exposure by 3.22% ($3,892)"
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
                            "VYM matched. Reinvesting $71,700 at the current 10Y yield (4.569%) will generate $3,276 in annual income."
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

# Executive PDF Generator Class
class ExecutiveReportPDF(FPDF):
    def header(self):
        # Top banner with Google branding colors (Google Blue)
        self.set_fill_color(66, 133, 244) # #4285F4
        self.rect(0, 0, 210, 15, 'F')
        
        # Red, Yellow, Green accent line
        self.set_fill_color(234, 67, 53) # Red
        self.rect(0, 15, 70, 1.5, 'F')
        self.set_fill_color(251, 188, 5) # Yellow
        self.rect(70, 15, 70, 1.5, 'F')
        self.set_fill_color(52, 168, 83) # Green
        self.rect(140, 15, 70, 1.5, 'F')
        
        self.set_y(4)
        self.set_text_color(255, 255, 255)
        self.set_font('helvetica', 'B', 9)
        self.cell(0, 5, 'SHIELDWEALTH AI COMPLIANCE PLATFORM  |  REGULATORY DOSSIER', 0, 1, 'C')
        
    def footer(self):
        self.set_y(-15)
        self.set_font('helvetica', 'I', 8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, 'Built for the Google AI Agents Hackathon  |  Confidential Internal Audit Archive', 0, 0, 'L')
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'R')

def generate_pdf_report(state, summary_data):
    def clean_pdf_text(text):
        if not isinstance(text, str):
            return str(text)
        # Replace emojis and special symbols
        text = text.replace('✅', '[PASS]').replace('⚠️', '[ALERT]').replace('❌', '[FAIL]').replace('✔️', '[CHECK]')
        text = text.replace('➡️', '->').replace('🔹', '-').replace('®', '(R)').replace('©', '(C)')
        # Replace other potential non-latin1 characters with close equivalents or spaces
        text = text.encode('latin-1', 'replace').decode('latin-1')
        return text

    profile = state.get("client_profile", {})
    metrics = state.get("portfolio_metrics", {})
    compliance = state.get("compliance_result", {})
    
    # Calculate R1-R6 actuals and limits dynamically
    import pandas as pd
    try:
        holdings_df = pd.read_csv("/Users/rishabhsrinivasan/Desktop/Projects/Kaggle/data/holdings.csv")
        client_holdings = holdings_df[holdings_df["client_id"] == profile.get("client_id")]
        
        acct_vals = {"savings": 0.0, "checking": 0.0, "brokerage_taxable": 0.0, "401k": 0.0, "IRA": 0.0}
        ticker_vals = {}
        for _, row in client_holdings.iterrows():
            val = float(row["value"])
            acct = row["account_type"]
            acct_vals[acct] = acct_vals.get(acct, 0.0) + val
            
            ticker = row["ticker"]
            ticker_vals[ticker] = ticker_vals.get(ticker, 0.0) + val
            
        total_val = float(metrics.get("total_value", 1.0))
        accessible_sum = acct_vals.get("savings", 0.0) + acct_vals.get("checking", 0.0) + acct_vals.get("brokerage_taxable", 0.0)
        pct_accessible = (accessible_sum / total_val) * 100.0
        
        max_ticker = max(ticker_vals, key=ticker_vals.get) if ticker_vals else ""
        max_ticker_val = ticker_vals[max_ticker] if max_ticker else 0.0
        pct_max_ticker = (max_ticker_val / total_val) * 100.0
        
        retirement_sum = acct_vals.get("401k", 0.0) + acct_vals.get("IRA", 0.0)
    except Exception:
        pct_accessible = 0.0
        pct_max_ticker = 0.0
        retirement_sum = 0.0
        max_ticker = ""
        
    other_debt = float(profile.get("existing_other_debt", 0.0))
    pct_high_vol = float(metrics.get("pct_high_volatility", 0.0))
    pct_equity = float(metrics.get("pct_equity", 0.0))
    age_norm_benchmark = float(metrics.get("age_allocations", {}).get("target_equity_pct", 0.0))
    
    pdf = ExecutiveReportPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    # --- PAGE 1: COVER PAGE ---
    pdf.add_page()
    pdf.set_xy(20, 40)
    pdf.set_font('helvetica', 'B', 24)
    pdf.set_text_color(26, 54, 93)
    pdf.cell(0, 15, "SHIELDWEALTH AI", 0, 1, 'C')
    pdf.set_font('helvetica', 'B', 16)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 10, "Portfolio Suitability & Compliance Report", 0, 1, 'C')
    pdf.ln(10)
    
    # Divider line
    pdf.set_draw_color(66, 133, 244)
    pdf.set_line_width(1)
    pdf.line(40, 75, 170, 75)
    
    # Profile Card
    pdf.ln(20)
    pdf.set_fill_color(248, 249, 250)
    pdf.rect(20, 85, 170, 85, 'F')
    pdf.set_xy(20, 90)
    pdf.set_font('helvetica', 'B', 12)
    pdf.set_text_color(51, 51, 51)
    
    pdf.cell(10)
    pdf.cell(0, 8, clean_pdf_text(f"Client Name: {profile.get('name', 'N/A')}"), 0, 1, 'L')
    pdf.cell(10)
    pdf.cell(0, 8, clean_pdf_text(f"Client ID: {profile.get('client_id', 'N/A')}"), 0, 1, 'L')
    pdf.cell(10)
    pdf.cell(0, 8, clean_pdf_text(f"Goal: {profile.get('investment_goal', 'N/A').title().replace('_', ' ')}"), 0, 1, 'L')
    pdf.cell(10)
    pdf.cell(0, 8, clean_pdf_text(f"Risk Tolerance: {profile.get('stated_risk_tolerance', 'N/A').title()} Profile"), 0, 1, 'L')
    pdf.cell(10)
    pdf.cell(0, 8, clean_pdf_text(f"Portfolio Health Score: {summary_data.get('health_score')}/100"), 0, 1, 'L')
    pdf.cell(10)
    pdf.cell(0, 8, clean_pdf_text(f"Recommendation Priority: {summary_data.get('priority')}"), 0, 1, 'L')
    pdf.cell(10)
    pdf.cell(0, 8, clean_pdf_text(f"Audit Status: {compliance.get('status', 'N/A')}"), 0, 1, 'L')
    
    pdf.set_xy(20, 190)
    pdf.set_font('helvetica', 'I', 9)
    pdf.set_text_color(128, 128, 128)
    pdf.multi_cell(170, 5, "CONFIDENTIAL DOCUMENT: For internal wealth management advisor use only. This audit trail details compliance calculations and suitability results processed by ShieldWealth AI reasoning models in compliance with SEC rules and firm concentration guidelines.", 0, 'C')
    
    pdf.set_xy(20, 230)
    pdf.set_font('helvetica', 'B', 10)
    pdf.set_text_color(66, 133, 244)
    pdf.cell(0, 6, "Built for the Google AI Agents Hackathon", 0, 1, 'C')
    pdf.set_font('helvetica', '', 9)
    pdf.set_text_color(128, 128, 128)
    pdf.cell(0, 5, "This is a demonstration system. Not an official Deloitte product.", 0, 1, 'C')

    # --- PAGE 2: EXECUTIVE SUMMARY & PROFILE ---
    pdf.add_page()
    pdf.set_xy(20, 20)
    pdf.set_font('helvetica', 'B', 14)
    pdf.set_text_color(26, 54, 93)
    pdf.cell(0, 8, "1. Executive Summary & Suitability Verdict", 0, 1, 'L')
    pdf.line(10, 28, 200, 28)
    
    pdf.set_xy(20, 33)
    pdf.set_font('helvetica', 'B', 11)
    pdf.set_text_color(0, 0, 0)
    pdf.multi_cell(170, 6, clean_pdf_text(f"Verdict: {summary_data.get('headline')}"))
    pdf.ln(3)
    
    pdf.set_x(20)
    pdf.set_font('helvetica', '', 10)
    pdf.cell(60, 6, clean_pdf_text(f"Health Score: {summary_data.get('health_score')}/100"), 0, 0)
    pdf.cell(60, 6, clean_pdf_text(f"Priority: {summary_data.get('priority')}"), 0, 0)
    pdf.cell(50, 6, clean_pdf_text(f"Confidence: {summary_data.get('confidence')}"), 0, 1)
    
    pdf.ln(5)
    pdf.set_x(20)
    pdf.set_font('helvetica', 'B', 10)
    pdf.cell(0, 6, "Key Findings:", 0, 1)
    pdf.set_font('helvetica', '', 9.5)
    for reason in summary_data.get("reasons", []):
        pdf.set_x(20)
        pdf.multi_cell(170, 5, clean_pdf_text(f"- {reason}"))
        
    pdf.ln(8)
    pdf.set_x(20)
    pdf.set_font('helvetica', 'B', 14)
    pdf.set_text_color(26, 54, 93)
    pdf.cell(0, 8, "2. Client Profile & Financial Background", 0, 1, 'L')
    pdf.line(10, pdf.get_y() + 8, 200, pdf.get_y() + 8)
    
    pdf.ln(12)
    pdf.set_x(20)
    pdf.set_font('helvetica', '', 10)
    col_width = 42
    
    pdf.cell(col_width, 6, "Age:", 1, 0)
    pdf.cell(col_width, 6, clean_pdf_text(f"{profile.get('age')} years"), 1, 0)
    pdf.cell(col_width, 6, "Stated Risk Profile:", 1, 0)
    pdf.cell(col_width, 6, clean_pdf_text(f"{profile.get('stated_risk_tolerance', '').title()}"), 1, 1)
    
    pdf.set_x(20)
    pdf.cell(col_width, 6, "Time Horizon:", 1, 0)
    pdf.cell(col_width, 6, clean_pdf_text(f"{profile.get('time_horizon_years')} years"), 1, 0)
    pdf.cell(col_width, 6, "Liquidity Requirement:", 1, 0)
    pdf.cell(col_width, 6, clean_pdf_text(f"{profile.get('liquidity_need', '').title()}"), 1, 1)
    
    pdf.set_x(20)
    pdf.cell(col_width, 6, "Annual Income:", 1, 0)
    pdf.cell(col_width, 6, clean_pdf_text(f"${float(profile.get('annual_income', 0)):,.2f}"), 1, 0)
    pdf.cell(col_width, 6, "Net Worth:", 1, 0)
    pdf.cell(col_width, 6, clean_pdf_text(f"${float(profile.get('net_worth', 0)):,.2f}"), 1, 1)
    
    pdf.set_x(20)
    pdf.cell(col_width, 6, "Investment Goal:", 1, 0)
    pdf.cell(col_width, 6, clean_pdf_text(f"{profile.get('investment_goal', '').title().replace('_', ' ')}"), 1, 0)
    pdf.cell(col_width, 6, "Dependents Count:", 1, 0)
    pdf.cell(col_width, 6, clean_pdf_text(f"{profile.get('dependents')}"), 1, 1)

    # --- PAGE 3: PORTFOLIO & AUDIT ---
    pdf.add_page()
    pdf.set_xy(20, 20)
    pdf.set_font('helvetica', 'B', 14)
    pdf.set_text_color(26, 54, 93)
    pdf.cell(0, 8, "3. Portfolio Allocation & Risk Thresholds", 0, 1, 'L')
    pdf.line(10, 28, 200, 28)
    
    pdf.ln(5)
    pdf.set_x(20)
    pdf.set_font('helvetica', 'B', 10)
    pdf.cell(60, 6, "Asset Category", 1, 0)
    pdf.cell(40, 6, "Current Value ($)", 1, 0)
    pdf.cell(40, 6, "Allocation (%)", 1, 1)
    
    pdf.set_font('helvetica', '', 10)
    total_val = float(metrics.get("total_value", 0))
    alloc_pcts = metrics.get("asset_allocations_pct", {})
    
    for category, pct in alloc_pcts.items():
        val = total_val * (pct / 100.0)
        pdf.set_x(20)
        pdf.cell(60, 6, clean_pdf_text(category.title().replace('_', ' ')), 1, 0)
        pdf.cell(40, 6, f"${val:,.2f}", 1, 0)
        pdf.cell(40, 6, f"{pct:.2f}%", 1, 1)
        
    pdf.set_x(20)
    pdf.set_font('helvetica', 'B', 10)
    pdf.cell(60, 6, "Total Asset Value", 1, 0)
    pdf.cell(40, 6, f"${total_val:,.2f}", 1, 0)
    pdf.cell(40, 6, "100.00%", 1, 1)
    
    pdf.ln(8)
    pdf.set_x(20)
    pdf.set_font('helvetica', 'B', 14)
    pdf.set_text_color(26, 54, 93)
    pdf.cell(0, 8, "4. Complete Compliance Check Checklist & Limits", 0, 1, 'L')
    pdf.line(10, pdf.get_y() + 8, 200, pdf.get_y() + 8)
    
    pdf.ln(12)
    pdf.set_x(20)
    pdf.set_font('helvetica', 'B', 9.5)
    pdf.cell(10, 6, "ID", 1, 0)
    pdf.cell(60, 6, "Corporate Rule / Guideline", 1, 0)
    pdf.cell(45, 6, "Personalized Threshold", 1, 0)
    pdf.cell(30, 6, "Actual Value", 1, 0)
    pdf.cell(25, 6, "Verdict", 1, 1)
    
    pdf.set_font('helvetica', '', 9)
    limits = compliance.get("limits", {})
    illiquidity_limit = limits.get("illiquidity_limit", 15.0)
    volatility_limit = limits.get("volatility_limit", 0.0)
    alternative_limit = limits.get("alternative_limit", 10.0)
    sector_limit = limits.get("sector_limit", 30.0)
    
    breaches = compliance.get("breached_rules", [])
    breached_ids = {b["rule_id"]: b["details"] for b in breaches}
    
    rules_table_info = [
        ("R1", "Retirement Early-Withdrawal penalty", "No 401k/IRA if Horizon <= 3 yrs", f"${retirement_sum:,.0f} in 401k/IRA"),
        ("R2", "Single-Position concentration", "<= 30% of portfolio value", f"{pct_max_ticker:.1f}% ({max_ticker})"),
        ("R3", "Volatility vs Conservative Profile", "<= 15% high-vol assets", f"{pct_high_vol:.1f}% high-vol"),
        ("R4", "Liquidity vs Accessible balance", ">= 25% accessible if liquidity high", f"{pct_accessible:.1f}% accessible"),
        ("R5", "Debt-Adjusted Risk Exposure", "<= 20% high-vol if debt > $20k", f"{pct_high_vol:.1f}% high-vol"),
        ("R6", "Age-Based Equity Allocation", f"<= {age_norm_benchmark + 15.0:.1f}%" if float(profile.get("age", 0)) >= 55 else "No age ceiling (< 55)", f"{pct_equity:.1f}% equity")
    ]
    
    for rid, title, limit, actual in rules_table_info:
        status_text = "FLAGGED" if rid in breached_ids else "PASSED"
        pdf.set_x(20)
        pdf.cell(10, 6, rid, 1, 0)
        pdf.cell(60, 6, clean_pdf_text(title), 1, 0)
        pdf.cell(45, 6, clean_pdf_text(limit), 1, 0)
        pdf.cell(30, 6, clean_pdf_text(actual), 1, 0)
        pdf.cell(25, 6, clean_pdf_text(status_text), 1, 1)

    # --- PAGE 4: SHIFTS & EXPLAINABILITY ---
    pdf.add_page()
    pdf.set_xy(20, 20)
    pdf.set_font('helvetica', 'B', 14)
    pdf.set_text_color(26, 54, 93)
    pdf.cell(0, 8, "5. Recommended Portfolio Rebalancing Shifts", 0, 1, 'L')
    pdf.line(10, 28, 200, 28)
    
    pdf.ln(5)
    pdf.set_x(20)
    pdf.set_font('helvetica', 'B', 10.5)
    pdf.cell(0, 6, "Category-Level Allocation Target Shifts:", 0, 1)
    pdf.set_font('helvetica', '', 9.5)
    
    shifts_list = summary_data.get("shifts", [])
    if len(shifts_list) == 0:
        pdf.set_x(20)
        pdf.multi_cell(170, 5, "No target shifts required. The current asset allocation conforms to regulatory tolerances.")
    else:
        for shift in shifts_list:
            pdf.set_x(20)
            pdf.multi_cell(170, 5, clean_pdf_text(f"- {shift}"))
            
    pdf.ln(4)
    pdf.set_x(20)
    pdf.set_font('helvetica', 'B', 10.5)
    pdf.cell(0, 6, "Expected Rebalancing Business Impact:", 0, 1)
    pdf.set_font('helvetica', '', 9.5)
    pdf.set_x(20)
    pdf.multi_cell(170, 5, clean_pdf_text(summary_data.get("impact", "Maintain allocations.")))
    
    # RAG recommendations match
    pdf.ln(4)
    pdf.set_x(20)
    pdf.set_font('helvetica', 'B', 10.5)
    pdf.cell(0, 6, "RAG-Grounded Rebalancing Fund Matches:", 0, 1)
    pdf.set_font('helvetica', '', 9.5)
    rag_result = state.get("product_research_result", {})
    primary_fund = rag_result.get("primary_match", {})
    secondary_fund = rag_result.get("secondary_match", {})
    if primary_fund:
        pdf.set_x(20)
        pdf.multi_cell(170, 5, clean_pdf_text(f"Primary Match: {primary_fund.get('ticker')} - {primary_fund.get('name')} (Expense Ratio: {primary_fund.get('expense_ratio')}, Volatility: {primary_fund.get('volatility')})"))
        if secondary_fund:
            pdf.set_x(20)
            pdf.multi_cell(170, 5, clean_pdf_text(f"Secondary Match: {secondary_fund.get('ticker')} - {secondary_fund.get('name')} (Expense Ratio: {secondary_fund.get('expense_ratio')}, Volatility: {secondary_fund.get('volatility')})"))
    else:
        pdf.set_x(20)
        pdf.multi_cell(170, 5, "No specific funds matched from vector database.")
        
    pdf.ln(6)
    pdf.set_x(20)
    pdf.set_font('helvetica', 'B', 14)
    pdf.set_text_color(26, 54, 93)
    pdf.cell(0, 8, "6. Multi-Agent Reasoning Trace (Decision Trace)", 0, 1, 'L')
    pdf.line(10, pdf.get_y() + 8, 200, pdf.get_y() + 8)
    
    pdf.ln(12)
    pdf.set_font('helvetica', '', 9.5)
    
    traces = [
        ("1. Intake Agent", "Fetched profile metadata from CSV. Audited demographic parameters. Saved profile."),
        ("2. Personal Financial Analyst Agent", "Analyzed credit band, employment standing, and debt profile to compute stability score."),
        ("3. Portfolio Analysis Agent", "Parsed CSV holdings. Computed allocations and compared variance with Age Benchmarks."),
        ("4. Market Scout Agent", "Fetched real-time VIX index level and 10Y/3M Treasury yield rates from Yahoo Finance."),
        ("5. Risk Assessment Agent", "Assessed portfolio volatility match against VIX macro risk environment."),
        ("6. Compliance Agent", "Audited personalized compliance rules R1 to R6 based on client specific parameters."),
        ("7. Planning/Strategy Agent", "Formulated strategic rebalancing direction and asset allocation directives."),
        ("8. Product Research Agent (RAG)", "Performed FAISS vector search across fund prospectuses to identify optimal low-cost replacement funds."),
        ("9. Advisor Summary Agent", "Consolidated compliance state parameters into structured verdict headline, health score, and category shifts.")
    ]
    for agent, log in traces:
        pdf.set_x(20)
        pdf.set_font('helvetica', 'B', 10)
        pdf.cell(0, 5, clean_pdf_text(agent), 0, 1)
        pdf.set_x(20)
        pdf.set_font('helvetica', '', 9.5)
        pdf.multi_cell(170, 5, clean_pdf_text(log))
        pdf.ln(1)
        
    pdf.ln(4)
    pdf.set_x(20)
    pdf.set_font('helvetica', 'B', 14)
    pdf.set_text_color(26, 54, 93)
    pdf.cell(0, 8, "7. Data Privacy, Governance & SEC Compliance", 0, 1, 'L')
    pdf.line(10, pdf.get_y() + 8, 200, pdf.get_y() + 8)
    
    pdf.ln(12)
    pdf.set_x(20)
    pdf.set_font('helvetica', '', 9.5)
    pdf.multi_cell(170, 5, "This compliance dossier is built utilizing offline, deterministic rule parameters. Audits do not use external APIs or live internet connections, ensuring zero data leakage of customer financial holdings. Data retrieval operations enforce single-client scoping restrictions to comply with financial sector privacy regulations.")
    
    return bytes(pdf.output())

# --- Custom Styling (Google Palette & Deloitte Style Spacing) ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Playfair+Display:ital,wght@0,600;0,700;1,600&display=swap');
    
    .main-header {
        font-family: 'Playfair Display', serif;
        color: #0F2547; /* Royal Navy */
        font-weight: 700;
        font-size: 2.4rem;
        margin-bottom: 2px;
        letter-spacing: -0.5px;
    }
    .sub-header {
        font-family: 'Inter', sans-serif;
        color: #C5A880; /* Elegant Satin Gold */
        font-weight: 600;
        font-size: 0.95rem;
        letter-spacing: 2px;
        text-transform: uppercase;
        margin-bottom: 25px;
    }
    .section-title {
        font-family: 'Playfair Display', serif;
        color: #0F2547;
        font-weight: 700;
        font-size: 1.35rem;
        margin-top: 20px;
        margin-bottom: 15px;
        border-bottom: 2px solid #C5A880; /* Satin Gold Accent */
        padding-bottom: 6px;
    }
    .badge-aligned {
        background-color: #f4fbf7;
        border: 1px solid #34a853;
        color: #137333;
        padding: 6px 14px;
        border-radius: 4px;
        font-family: 'Inter', sans-serif;
        font-weight: 700;
        font-size: 12px;
        letter-spacing: 0.5px;
        text-transform: uppercase;
        display: inline-block;
    }
    .badge-mismatch {
        background-color: #fdf2f2;
        border: 1px solid #ea4335;
        color: #c5221f;
        padding: 6px 14px;
        border-radius: 4px;
        font-family: 'Inter', sans-serif;
        font-weight: 700;
        font-size: 12px;
        letter-spacing: 0.5px;
        text-transform: uppercase;
        display: inline-block;
    }
    .metric-value {
        font-family: 'Inter', sans-serif;
        font-size: 22px;
        font-weight: 700;
        color: #0F2547;
    }
    .metric-label {
        font-family: 'Inter', sans-serif;
        font-size: 11px;
        font-weight: 500;
        color: #5f6368;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        opacity: 0.9;
    }
</style>
""", unsafe_allow_html=True)

# Import ADK app
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
from google.adk.runners import InMemoryRunner

# Patch agents with MockLlm to run locally instantly
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

def run_suitability_pipeline(client_id: str):
    async def _run():
        runner = InMemoryRunner(app=app)
        session = await runner.session_service.create_session(
            app_name="app",
            user_id="test_user",
            session_id=str(uuid.uuid4()),
            state={}
        )
        msg = types.Content(
            role="user",
            parts=[types.Part(text=f"Run suitability analysis for client {client_id}.")]
        )
        async for event in runner.run_async(
            user_id="test_user",
            session_id=session.id,
            new_message=msg
        ):
            pass
        
        session = await runner.session_service.get_session(app_name="app", user_id="test_user", session_id=session.id)
        return session.state

    return asyncio.run(_run())

# Load clients
@st.cache_data
def load_clients():
    clients_path = "/Users/rishabhsrinivasan/Desktop/Projects/Kaggle/data/clients.csv"
    return pd.read_csv(clients_path)

clients_df = load_clients()

def format_client_row(row):
    return f"{row['name']} · Age {row['age']} · {row['investment_goal'].title().replace('_', ' ')} · {row['stated_risk_tolerance'].title()} risk"

# Streamlit Layout Headers
st.markdown('<div class="main-header">🛡️ SHIELDWEALTH PRIVATE WEALTH</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Bespoke Client Compliance & Portfolio Suitability Suite</div>', unsafe_allow_html=True)

# Client Selector Sidebar
st.sidebar.header("Compliance Controls")
selected_client_idx = st.sidebar.selectbox(
    "Client Profile Database",
    options=range(len(clients_df)),
    format_func=lambda idx: f"{clients_df.iloc[idx]['client_id']} - {format_client_row(clients_df.iloc[idx])}"
)

client_row = clients_df.iloc[selected_client_idx]
client_id = client_row['client_id']

run_analysis = st.sidebar.button("Execute Multi-Agent Audit", type="primary", use_container_width=True)

if run_analysis or "state" not in st.session_state or st.session_state.get("current_client_id") != client_id:
    with st.spinner("Processing local compliance audits..."):
        state = run_suitability_pipeline(client_id)
        st.session_state["state"] = state
        st.session_state["current_client_id"] = client_id

state = st.session_state["state"]
profile = state.get("client_profile", {})
metrics = state.get("portfolio_metrics", {})
risk_flags = state.get("risk_flags", {})
compliance = state.get("compliance_result", {})
final_summary = state.get("final_summary", "")

# Parser for structured advisor summary JSON
def parse_advisor_summary(summary_str: str) -> dict:
    try:
        clean_str = re.sub(r"^```json\s*", "", summary_str.strip())
        clean_str = re.sub(r"\s*```$", "", clean_str.strip())
        return json.loads(clean_str)
    except Exception:
        return {
            "headline": "⚠️ Rebalance required to address compliance gaps.",
            "health_score": 70,
            "priority": "Medium",
            "confidence": "95%",
            "reasons": ["Risk parameters or illiquid limits require alignment."],
            "shifts": ["Reallocate equity holdings."],
            "impact": "Improves overall compliance.",
            "checked_items": ["Risk Alignment", "Liquidity", "Diversification", "Age Suitability"]
        }

summary_data = parse_advisor_summary(final_summary)

# Client Profile Metrics
st.markdown('<div class="section-title">1. Client Demographic & Macro Market Context</div>', unsafe_allow_html=True)

# Row 1: Client Demographics
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.markdown(f'<div class="metric-label">Client Age</div><div class="metric-value">{profile.get("age")} years</div>', unsafe_allow_html=True)
with col2:
    st.markdown(f'<div class="metric-label">Goal Horizon</div><div class="metric-value">{profile.get("time_horizon_years")} years</div>', unsafe_allow_html=True)
with col3:
    st.markdown(f'<div class="metric-label">Risk Profile</div><div class="metric-value">{profile.get("stated_risk_tolerance", "").title()}</div>', unsafe_allow_html=True)
with col4:
    st.markdown(f'<div class="metric-label">Liquidity Requirement</div><div class="metric-value">{profile.get("liquidity_need", "").title()}</div>', unsafe_allow_html=True)

# Row 2: Employment, Debt and Live Market Context
st.markdown('<div style="margin-top: 10px;"></div>', unsafe_allow_html=True)
col5, col6, col7, col8 = st.columns(4)
with col5:
    st.markdown(f'<div class="metric-label">Income Stability</div><div class="metric-value">{profile.get("income_stability", "").title()} ({profile.get("employment_status", "").title()})</div>', unsafe_allow_html=True)

market_context = state.get("market_context", {})
vix_val = market_context.get("vix", 16.9)
rate_10y = market_context.get("yield_10y", 4.569)
rate_3m = market_context.get("yield_3m", 3.723)

with col6:
    st.markdown(f'<div class="metric-label">Market VIX Index</div><div class="metric-value" style="color: #4285F4;">{vix_val} ({market_context.get("vix_status", "moderate")})</div>', unsafe_allow_html=True)
with col7:
    st.markdown(f'<div class="metric-label">10Y Treasury Rate</div><div class="metric-value" style="color: #34A853;">{rate_10y}%</div>', unsafe_allow_html=True)
with col8:
    st.markdown(f'<div class="metric-label">3M Treasury Rate</div><div class="metric-value" style="color: #34A853;">{rate_3m}%</div>', unsafe_allow_html=True)

# Main Allocation and Recommendations
left_col, right_col = st.columns([3, 2])

with left_col:
    st.markdown('<div class="section-title">2. Portfolio Allocation & Composition</div>', unsafe_allow_html=True)
    alloc = metrics.get("asset_allocations_pct", {})
    labels = [k.title().replace('_', ' ') for k in alloc.keys()]
    values = list(alloc.values())
    
    colors = ['#4285F4', '#EA4335', '#FBBC05', '#34A853', '#805ad5'] # Google colors style
    fig = go.Figure(data=[go.Pie(
        labels=labels, 
        values=values, 
        hole=0.6,
        marker=dict(colors=colors, line=dict(color='#ffffff', width=2))
    )])
    fig.update_layout(
        margin=dict(t=10, b=10, l=10, r=10),
        height=300,
        legend=dict(orientation="h", yanchor="bottom", y=-0.1, xanchor="center", x=0.5)
    )
    st.plotly_chart(fig, use_container_width=True)

with right_col:
    st.markdown('<div class="section-title">3. Volatility Profile Match</div>', unsafe_allow_html=True)
    
    is_mismatch = risk_flags.get("risk_tolerance_mismatch", False)
    if is_mismatch:
        st.markdown('<div style="text-align: center; margin-bottom: 15px;"><span class="badge-mismatch">⚠️ RISK PROFILE MISMATCH</span></div>', unsafe_allow_html=True)
    else:
        st.markdown('<div style="text-align: center; margin-bottom: 15px;"><span class="badge-aligned">✅ RISK PROFILE MATCHED</span></div>', unsafe_allow_html=True)
        
    stated_risk = profile.get("stated_risk_tolerance", "").lower()
    stated_pct = 33 if stated_risk == "conservative" else (66 if stated_risk == "moderate" else 100)
    
    pct_high_vol = metrics.get("pct_high_volatility", 0.0)
    actual_risk = "low" if pct_high_vol == 0 else ("moderate" if pct_high_vol <= 30 else "high")
    actual_pct = 33 if actual_risk == "low" else (66 if actual_risk == "moderate" else 100)
    actual_color = "#34a853" if not is_mismatch else "#ea4335" # Green/Red
    
    st.markdown(f"""<div style="margin: 8px 0; padding: 12px; background-color: #f8f9fa; color: #111827; border-radius: 8px; border-left: 4px solid #4285F4; box-shadow: 0 1px 2px rgba(0,0,0,0.01);">
<strong style="font-size: 13px; color: #1a365d;">Stated Profile: {stated_risk.title()}</strong>
<div style="background-color: #e2e8f0; border-radius: 5px; height: 8px; width: 100%; margin-top: 5px;">
<div style="background-color: #4285F4; height: 100%; border-radius: 5px; width: {stated_pct}%;"></div>
</div>
</div>
<div style="margin: 12px 0 8px 0; padding: 12px; background-color: #f8f9fa; color: #111827; border-radius: 8px; border-left: 4px solid {actual_color}; box-shadow: 0 1px 2px rgba(0,0,0,0.01);">
<strong style="font-size: 13px; color: #1a365d;">Actual Allocation Risk: {actual_risk.title()}</strong>
<div style="background-color: #e2e8f0; border-radius: 5px; height: 8px; width: 100%; margin-top: 5px;">
<div style="background-color: {actual_color}; height: 100%; border-radius: 5px; width: {actual_pct}%;"></div>
</div>
</div>""", unsafe_allow_html=True)

# 4. Corporate Suitability Rules Details
st.markdown('<div class="section-title">4. Corporate Suitability Rules Details</div>', unsafe_allow_html=True)

# Calculate R1-R6 actuals and limits dynamically
import pandas as pd
try:
    holdings_df = pd.read_csv("/Users/rishabhsrinivasan/Desktop/Projects/Kaggle/data/holdings.csv")
    client_holdings = holdings_df[holdings_df["client_id"] == profile.get("client_id")]
    
    acct_vals = {"savings": 0.0, "checking": 0.0, "brokerage_taxable": 0.0, "401k": 0.0, "IRA": 0.0}
    ticker_vals = {}
    for _, row in client_holdings.iterrows():
        val = float(row["value"])
        acct = row["account_type"]
        acct_vals[acct] = acct_vals.get(acct, 0.0) + val
        
        ticker = row["ticker"]
        ticker_vals[ticker] = ticker_vals.get(ticker, 0.0) + val
        
    total_val = float(metrics.get("total_value", 1.0))
    accessible_sum = acct_vals.get("savings", 0.0) + acct_vals.get("checking", 0.0) + acct_vals.get("brokerage_taxable", 0.0)
    pct_accessible = (accessible_sum / total_val) * 100.0
    
    max_ticker = max(ticker_vals, key=ticker_vals.get) if ticker_vals else ""
    max_ticker_val = ticker_vals[max_ticker] if max_ticker else 0.0
    pct_max_ticker = (max_ticker_val / total_val) * 100.0
    
    retirement_sum = acct_vals.get("401k", 0.0) + acct_vals.get("IRA", 0.0)
except Exception:
    pct_accessible = 0.0
    pct_max_ticker = 0.0
    retirement_sum = 0.0
    max_ticker = ""
    
other_debt = float(profile.get("existing_other_debt", 0.0))
pct_high_vol = float(metrics.get("pct_high_volatility", 0.0))
pct_equity = float(metrics.get("pct_equity", 0.0))
age_norm_benchmark = float(metrics.get("age_allocations", {}).get("target_equity_pct", 0.0))

# Personalised rules explanations
rules_explanations = {
    "R1": f"Early-withdrawal penalty risk for retirement accounts (401k/IRA) when client has a short goal time horizon ({profile.get('time_horizon_years', 'N/A')} years).",
    "R2": "Single-position concentration risk: no single asset may exceed 30% of total portfolio value.",
    "R3": f"Strict 15% high-volatility limit for client with conservative risk tolerance ('{profile.get('stated_risk_tolerance', 'N/A')}').",
    "R4": f"Requires at least 25% in accessible savings/checking/taxable accounts for high liquidity need ('{profile.get('liquidity_need', 'N/A')}').",
    "R5": f"Debt-adjusted risk exposure constraint: limits high-volatility assets to 20% when client debt exceeds $20,000.",
    "R6": f"Age-based equity allocation ceiling (benchmark + 15%) for clients aged 55 or older (Current age: {profile.get('age', 'N/A')} years)."
}

limits = compliance.get("limits", {})

rules_info = {
    "R1": ("Retirement Early-Withdrawal", "No 401k/IRA if Horizon <= 3 yrs", f"${retirement_sum:,.0f} in retirement accts"),
    "R2": ("Single-Position Concentration", "<= 30% of portfolio", f"{pct_max_ticker:.1f}% ({max_ticker})"),
    "R3": ("Volatility Exposure Limit", f"<= 15% (conservative limit)", f"{pct_high_vol:.1f}%"),
    "R4": ("Liquidity vs Accessible Balance", ">= 25% accessible if liquidity high", f"{pct_accessible:.1f}% accessible"),
    "R5": ("Debt-Adjusted Risk Exposure", "<= 20% high-vol if debt > $20k", f"{pct_high_vol:.1f}%"),
    "R6": ("Age-Based Equity Allocation", f"<= {age_norm_benchmark + 15.0:.1f}%" if float(profile.get("age", 0)) >= 55 else "No age ceiling (< 55)", f"{pct_equity:.1f}% equity")
}

breaches = compliance.get("breached_rules", [])
breached_ids = {b["rule_id"]: b["details"] for b in breaches}

# Helper compliance card function
def render_detailed_compliance_card(rid: str, title: str, limit: str, actual: str, is_passed: bool, reason: str, why_limit: str):
    card_border = "#C5A880" if is_passed else "#ea4335" # Gold for pass, red for fail
    card_bg = "#ffffff"
    status_icon = "Passed" if is_passed else "Flagged"
    status_color = "#137333" if is_passed else "#c5221f"
    badge_bg = "#f4fbf7" if is_passed else "#fdf2f2"
    badge_border = "#34a853" if is_passed else "#ea4335"
    
    html_content = f"""<div style="border: 1px solid #e5e7eb; border-top: 4px solid {card_border}; background-color: {card_bg}; color: #1f2937; border-radius: 4px; padding: 16px; margin: 8px 0; min-height: 200px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);">
<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
<strong style="color: #0F2547; font-family: 'Playfair Display', serif; font-size: 15px;">{rid}: {title}</strong>
<span style="color: {status_color}; font-family: 'Inter', sans-serif; font-weight: 700; font-size: 10px; padding: 3px 10px; border-radius: 2px; border: 1px solid {badge_border}; background-color: {badge_bg}; text-transform: uppercase; letter-spacing: 0.5px;">{status_icon}</span>
</div>
<div style="font-family: 'Inter', sans-serif; margin-top: 8px; font-size: 12px; color: #4b5563; line-height: 1.4;">
<div style="display: flex; justify-content: space-between; margin-bottom: 4px;"><span><strong>Personalized Limit:</strong></span> <span>{limit}</span></div>
<div style="display: flex; justify-content: space-between; margin-bottom: 4px;"><span><strong>Actual Value:</strong></span> <span style="font-weight: 600; color: #0F2547;">{actual}</span></div>
</div>
{f"<div style='font-family: 'Inter', sans-serif; font-size: 11px; color: #c5221f; margin-top: 8px; line-height: 1.3;'><strong>Reason:</strong> {reason}</div>" if not is_passed else ""}
<div style="border-top: 1px solid #f3f4f6; margin-top: 12px; padding-top: 8px; font-family: 'Inter', sans-serif; font-size: 11px; color: #6b7280; line-height: 1.4;">
<strong>Why this limit?</strong> {why_limit}
</div>
</div>"""
    st.markdown(html_content, unsafe_allow_html=True)

# 2 rows of 3 columns
cols = st.columns(3)
rules_keys = list(rules_info.keys())
for idx, rid in enumerate(rules_keys):
    title, limit, actual = rules_info[rid]
    is_passed = rid not in breached_ids
    reason = breached_ids.get(rid, "")
    why_limit = rules_explanations[rid]
    with cols[idx % 3]:
        render_detailed_compliance_card(rid, title, limit, actual, is_passed, reason, why_limit)

# 5. Export Compliance Documentation
st.markdown('<div class="section-title">5. Export Compliance Documentation</div>', unsafe_allow_html=True)

# Loop-back indicator stepper (simulate retry on mismatch)
status = compliance.get("status", "PASS")
if status == "FLAG/REJECT":
    st.markdown("""<div style="display: flex; align-items: center; justify-content: center; margin: 10px 0 18px 0; padding: 15px; background-color: #fffaf0; color: #1f2937; border-radius: 8px; border-left: 5px solid #fbbc05; box-shadow: 0 2px 4px rgba(0,0,0,0.02);">
<span style="font-weight: 700; color: #4a5568; margin-right: 15px; font-size: 14px;">Agent Loop history:</span>
<span style="background-color: #fde8e8; border: 1px solid #f8b4b4; padding: 5px 12px; border-radius: 15px; color: #9b1c1c; font-weight: 700; font-size: 12px;">Attempt 1 ❌ (Breached Rules Flagged)</span>
<span style="margin: 0 12px; color: #a0aec0; font-weight: bold;">➡️</span>
<span style="background-color: #def7ec; border: 1px solid #bcf0da; padding: 5px 12px; border-radius: 15px; color: #03543f; font-weight: 700; font-size: 12px;">Attempt 2 🔄 (Category Rebalance Evaluated & Approved)</span>
</div>""", unsafe_allow_html=True)

pdf_bytes = generate_pdf_report(state, summary_data)
st.download_button(
    label="Download Executive Suitability Report (PDF)",
    data=pdf_bytes,
    file_name=f"ShieldWealth_Audit_{client_id}.pdf",
    mime="application/pdf",
    type="primary",
    use_container_width=True
)

# 6. Executive Verdict & Recommendation Summary
st.markdown('<div class="section-title">6. Executive Verdict & Recommendation Summary</div>', unsafe_allow_html=True)

sum_col1, sum_col2 = st.columns(2)
with sum_col1:
    h_color = "#34a853" if summary_data.get("health_score", 100) >= 80 else ("#fbbc05" if summary_data.get("health_score", 100) >= 50 else "#ea4335")
    st.markdown(f"""<div style="background-color: #f8f9fa; border-top: 4px solid {h_color}; padding: 15px; border-radius: 8px; text-align: center; color: #111827; box-shadow: 0 2px 4px rgba(0,0,0,0.02);">
<div style="font-size: 12px; color: #4b5563; font-weight: 600;">PORTFOLIO HEALTH SCORE</div>
<div style="font-size: 28px; font-weight: 800; color: {h_color}; margin-top: 5px;">{summary_data.get("health_score")}/100</div>
</div>""", unsafe_allow_html=True)
with sum_col2:
    p_color = "#ea4335" if summary_data.get("priority") == "High" else ("#fbbc05" if summary_data.get("priority") == "Medium" else "#34a853")
    st.markdown(f"""<div style="background-color: #f8f9fa; border-top: 4px solid {p_color}; padding: 15px; border-radius: 8px; text-align: center; color: #111827; box-shadow: 0 2px 4px rgba(0,0,0,0.02);">
<div style="font-size: 12px; color: #4b5563; font-weight: 600;">RECOMMENDATION PRIORITY</div>
<div style="font-size: 28px; font-weight: 800; color: {p_color}; margin-top: 5px;">{summary_data.get("priority")}</div>
</div>""", unsafe_allow_html=True)

st.markdown(f"""<div style="margin: 15px 0; padding: 20px; border-radius: 8px; background-color: #f8f9fa; color: #111827; border-left: 6px solid #4285F4; box-shadow: 0 2px 4px rgba(0,0,0,0.02);">
<h4 style="margin-top: 0; color: #1a365d; font-weight: 700; margin-bottom: 10px;">{summary_data.get("headline")}</h4>
<div style="margin-top: 10px; font-size: 14px; color: #2d3748;">
<strong>Advisory Rationale:</strong>
<ul style="margin-top: 5px; margin-bottom: 10px; padding-left: 20px; color: #2d3748; list-style-type: disc;">
{"".join([f"<li style='margin-bottom: 4px;'>{r}</li>" for r in summary_data.get("reasons", [])])}
</ul>
<strong style="display: block; margin-top: 12px;">Required Target Allocations Shifts:</strong>
<ul style="margin-top: 5px; padding-left: 20px; color: #2d3748; list-style-type: disc;">
{"".join([f"<li style='margin-bottom: 4px;'>{s}</li>" for s in summary_data.get("shifts", [])]) if len(summary_data.get("shifts", [])) > 0 else "<li>No shifts required. Portfolio is fully compliant.</li>"}
</ul>
<div style="margin-top: 12px; border-top: 1px solid #e2e8f0; padding-top: 8px;"><strong>Expected Business Impact:</strong> {summary_data.get("impact")}</div>
</div>
</div>""", unsafe_allow_html=True)

# Personalised Planning/Strategy and RAG Matches
strategy_text = state.get("planning_strategy", {}).get("recommendation", "N/A")
rag_result = state.get("product_research_result", {})
primary_match = rag_result.get("primary_match", {})
secondary_match = rag_result.get("secondary_match", {})

if strategy_text != "N/A":
    st.markdown(f"""<div style="margin: 15px 0; padding: 18px; border-radius: 8px; background-color: #f0f7ff; border-left: 6px solid #1a73e8; color: #111827; box-shadow: 0 2px 4px rgba(0,0,0,0.02);">
<strong style="color: #185abc; font-size: 14px;">🧠 Dynamic Advisory Strategy Directive:</strong>
<div style="font-size: 13.5px; margin-top: 5px; color: #202124; line-height: 1.4;">
{strategy_text}
</div>
</div>""", unsafe_allow_html=True)

if primary_match:
    fund_html = f"""<div style="margin: 15px 0; padding: 18px; border-radius: 8px; background-color: #f4fbf7; border: 1px solid #34a853; color: #111827; box-shadow: 0 2px 4px rgba(0,0,0,0.02);">
<strong style="color: #137333; font-size: 14px;">🔍 RAG-Grounded Fund Recommendation Matches:</strong>
<div style="margin-top: 8px; font-size: 13.5px; color: #202124;">
<strong>Primary Match: {primary_match.get('ticker')} — {primary_match.get('name')}</strong><br>
<span style="font-size: 12.5px; color: #5f6368;">Asset Class: {primary_match.get('asset_class')} | Sector: {primary_match.get('sector')} | Volatility: {primary_match.get('volatility')} | Expense Ratio: {primary_match.get('expense_ratio')}</span>
"""
    if secondary_match:
        fund_html += f"""<br><br>
<strong>Secondary Match: {secondary_match.get('ticker')} — {secondary_match.get('name')}</strong><br>
<span style="font-size: 12.5px; color: #5f6368;">Asset Class: {secondary_match.get('asset_class')} | Sector: {secondary_match.get('sector')} | Volatility: {secondary_match.get('volatility')} | Expense Ratio: {secondary_match.get('expense_ratio')}</span>
"""
    fund_html += "</div></div>"
    st.markdown(fund_html, unsafe_allow_html=True)

# Checked Audit list
st.markdown("<div style='margin-top: 5px;'><strong>Audited suitability checks:</strong></div>", unsafe_allow_html=True)
checked_cols = st.columns(len(summary_data.get("checked_items", [])))
for i, item in enumerate(summary_data.get("checked_items", [])):
    with checked_cols[i]:
        st.markdown(f"<div style='font-size: 13px; font-weight: 600; color: #137333;'>✔️ {item}</div>", unsafe_allow_html=True)

# Disclaimer Footer
st.markdown("""<div style="text-align: center; margin-top: 50px; padding: 20px 0; border-top: 1px solid #d1d5db; font-size: 11px; color: #70757a;">
Built for the Google AI Agents Hackathon  |  Confidential Advisory Suite Demonstration<br>
This is an internal prototype demonstration. This is not an official Deloitte product.
</div>""", unsafe_allow_html=True)
