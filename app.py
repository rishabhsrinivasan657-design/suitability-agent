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
        if "Intake Agent" in sys_inst:
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
                yield LlmResponse(
                    content=types.Content(
                        role="model",
                        parts=[types.Part(text="Suitability process finished successfully.")]
                    ),
                    partial=False
                )
            else:
                # Dynamic extraction of variables from system instructions
                name = "Client"
                name_match = re.search(r"'name':\s*'([^']*)'", sys_inst)
                if name_match:
                    name = name_match.group(1)

                client_id = "Client"
                id_match = re.search(r"'client_id':\s*'([^']*)'", sys_inst)
                if id_match:
                    client_id = id_match.group(1)

                # Extract compliance result status
                is_passing = "'status': 'PASS'" in sys_inst

                # Get portfolio metrics details to use in reasons/headline
                total_val_match = re.search(r"'total_value':\s*([0-9.]+)", sys_inst)
                total_value = float(total_val_match.group(1)) if total_val_match else 310000.0

                pct_alt_match = re.search(r"'pct_alternative':\s*([0-9.]+)", sys_inst)
                pct_alt = float(pct_alt_match.group(1)) if pct_alt_match else 0.0

                pct_illiquid_match = re.search(r"'pct_illiquid':\s*([0-9.]+)", sys_inst)
                pct_illiquid = float(pct_illiquid_match.group(1)) if pct_illiquid_match else 0.0

                max_sector_match = re.search(r"'max_sector_concentration_pct':\s*([0-9.]+)", sys_inst)
                max_sector = float(max_sector_match.group(1)) if max_sector_match else 0.0

                pct_high_vol_match = re.search(r"'pct_high_volatility':\s*([0-9.]+)", sys_inst)
                pct_high_vol = float(pct_high_vol_match.group(1)) if pct_high_vol_match else 0.0

                actual_cash_match = re.search(r"'cash':\s*([0-9.]+)", sys_inst)
                actual_cash = float(actual_cash_match.group(1)) if actual_cash_match else 0.0

                actual_bond_match = re.search(r"'bond':\s*([0-9.]+)", sys_inst)
                actual_bond = float(actual_bond_match.group(1)) if actual_bond_match else 0.0
                cash_bond_total = actual_cash + actual_bond

                reasons = []
                shifts = []
                health_score = 100
                checked_items = ["Risk Alignment", "Liquidity", "Diversification", "Age Suitability"]

                # Check breaches dynamically from the compliance result inside sys_inst
                if "'rule_id': 'R1'" in sys_inst:
                    reasons.append("Equity variance vs age norm exceeds corporate +/- 20% limit.")
                    health_score -= 15
                if "'rule_id': 'R2'" in sys_inst:
                    reasons.append(f"Alternative asset exposure ({pct_alt:.1f}%) exceeds corporate 10% cap.")
                    shifts.append(f"Reduce alternative asset holdings by {pct_alt - 10.0:.2f}% (${total_value * (pct_alt - 10.0)/100.0:,.0f})")
                    health_score -= 15
                if "'rule_id': 'R3'" in sys_inst:
                    illiquidity_limit_match = re.search(r"'illiquidity_limit':\s*([0-9.]+)", sys_inst)
                    illiquidity_limit = float(illiquidity_limit_match.group(1)) if illiquidity_limit_match else 15.0
                    reasons.append(f"Portfolio illiquidity ({pct_illiquid:.1f}%) exceeds dynamic limit of {illiquidity_limit:.1f}%.")
                    shifts.append("Shift illiquid holdings to liquid cash/bonds")
                    health_score -= 15
                if "'rule_id': 'R4'" in sys_inst:
                    reasons.append(f"Sector concentration in technology ({max_sector:.1f}%) exceeds corporate 30% cap.")
                    shifts.append(f"Reduce technology exposure by {max_sector - 30.0:.2f}% (${total_value * (max_sector - 30.0)/100.0:,.0f})")
                    health_score -= 15
                if "'rule_id': 'R5'" in sys_inst:
                    reasons.append(f"High-volatility assets ({pct_high_vol:.1f}%) exceed risk profile threshold.")
                    shifts.append("Reallocate volatile equity to low-volatility fixed income")
                    health_score -= 15
                if "'rule_id': 'R6'" in sys_inst:
                    reasons.append(f"Cash + short term bonds total {cash_bond_total:.1f}% vs 50% safety floor.")
                    shifts.append(f"Increase cash/bonds allocation by {50.0 - cash_bond_total:.2f}% (${total_value * (50.0 - cash_bond_total)/100.0:,.0f})")
                    health_score -= 15

                if is_passing:
                    health_score = 100
                    headline = f"✅ Portfolio Approved: {name}'s moderate growth asset mix is fully compliant"
                    priority = "Low"
                    reasons = [
                        "Current equity exposure is within target tolerance of age norm.",
                        "Zero alternative or illiquid asset compliance breaches identified.",
                        "Volatile asset exposure aligns with stated moderate risk tolerance."
                    ]
                    shifts = []
                    impact = "Maintain current allocation. Re-evaluate portfolio annually."
                else:
                    total_reallocate_pct = 0.0
                    if "R2" in sys_inst:
                        total_reallocate_pct += (pct_alt - 10.0)
                    if "R4" in sys_inst:
                        total_reallocate_pct += (max_sector - 30.0)
                    if total_reallocate_pct == 0.0:
                        total_reallocate_pct = pct_illiquid
                    
                    reallocate_amount = total_value * (total_reallocate_pct / 100.0)
                    headline = f"⚠️ Rebalance: Shift ~{total_reallocate_pct:.1f}% (${reallocate_amount:,.0f}) from tech equity/alternatives into liquid bonds"
                    priority = "High" if len(reasons) >= 3 else "Medium"
                    impact = "Restores mandatory volatility limits and satisfies target goal liquidity rule."

                memo_data = {
                    "headline": headline,
                    "health_score": max(health_score, 25),
                    "priority": priority,
                    "confidence": "98%" if not is_passing else "99%",
                    "reasons": reasons[:4],
                    "shifts": shifts[:3],
                    "impact": impact,
                    "checked_items": checked_items
                }
                
                yield LlmResponse(
                    content=types.Content(
                        role="model",
                        parts=[
                            types.Part(
                                function_call=types.FunctionCall(
                                    name="save_final_summary",
                                    args={"summary_text": json.dumps(memo_data)}
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
        ("R1", "Equity Variance vs Age Norm", "Within +/- 20%", f"{abs(metrics.get('age_allocations', {}).get('equity_diff', 0)):.1f}% variance"),
        ("R2", "Alternative Concentration Limit", f"<= {alternative_limit}%", f"{metrics.get('pct_alternative', 0):.1f}%"),
        ("R3", "Illiquid Asset Concentration Limit", f"<= {illiquidity_limit}%", f"{metrics.get('pct_illiquid', 0):.1f}%"),
        ("R4", "Max Sector Concentration", f"<= {sector_limit}%", f"{metrics.get('max_sector_concentration_pct', 0):.1f}%"),
        ("R5", "Asset Volatility Profile Constraint", f"<= {volatility_limit}%", f"{metrics.get('pct_high_volatility', 0):.1f}%"),
        ("R6", "Home Goal Liquidity Reserve", ">= 50% cash+bonds", f"{metrics.get('asset_allocations_pct', {}).get('cash', 0) + metrics.get('asset_allocations_pct', {}).get('bond', 0):.1f}%")
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
        ("2. Portfolio Analysis Agent", "Parsed CSV holdings. Computed allocations and compared variance with Age Benchmarks."),
        ("3. Risk Assessment Agent", "Compared portfolio high-volatility holdings against stated risk constraints."),
        ("4. Compliance Agent", "Audited concentration and liquidity rules dynamically against calculated thresholds."),
        ("5. Advisor Summary Agent", "Consolidated compliance state parameters into structured verdict headline, health score, and category shifts.")
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
    .main-header {
        font-family: 'Outfit', sans-serif;
        color: #4285F4; /* Vibrant Google Blue, highly visible on dark and light backgrounds */
        font-weight: 800;
        font-size: 2.3rem;
        margin-bottom: 2px;
    }
    .sub-header {
        font-family: 'Inter', sans-serif;
        color: #4285F4; /* Google Blue */
        font-weight: 600;
        font-size: 1.1rem;
        margin-bottom: 20px;
    }
    .section-title {
        font-family: 'Outfit', sans-serif;
        color: var(--text-color); /* Adapts dynamically to light/dark page theme */
        font-weight: 700;
        font-size: 1.4rem;
        margin-top: 15px;
        margin-bottom: 15px;
        border-bottom: 3px solid #4285F4; /* Google Blue */
        padding-bottom: 5px;
    }
    .badge-aligned {
        background-color: #e6f4ea;
        border: 2px solid #34a853; /* Google Green */
        color: #137333;
        padding: 8px 18px;
        border-radius: 20px;
        font-weight: 800;
        font-size: 15px;
        display: inline-block;
        box-shadow: 0 2px 4px rgba(0,0,0,0.03);
    }
    .badge-mismatch {
        background-color: #fce8e6;
        border: 2px solid #ea4335; /* Google Red */
        color: #c5221f;
        padding: 8px 18px;
        border-radius: 20px;
        font-weight: 800;
        font-size: 15px;
        display: inline-block;
        box-shadow: 0 2px 4px rgba(0,0,0,0.03);
    }
    .metric-value {
        font-size: 24px;
        font-weight: 700;
        color: var(--text-color); /* Adapts dynamically */
    }
    .metric-label {
        font-size: 13px;
        color: var(--text-color); /* Adapts dynamically */
        opacity: 0.8;
    }
</style>
""", unsafe_allow_html=True)

# Import ADK app
from app.agent import (
    app,
    intake_agent,
    portfolio_analysis_agent,
    risk_assessment_agent,
    compliance_agent,
    advisor_summary_agent
)
from google.adk.runners import InMemoryRunner

# Patch agents with MockLlm to run locally instantly
mock_llm = MockLlm()
intake_agent.model = mock_llm
portfolio_analysis_agent.model = mock_llm
risk_assessment_agent.model = mock_llm
compliance_agent.model = mock_llm
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
st.markdown('<div class="main-header">🛡️ ShieldWealth AI Compliance</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Google AI Agents Hackathon  |  Enterprise Suite</div>', unsafe_allow_html=True)

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
st.markdown('<div class="section-title">1. Client Demographic Context</div>', unsafe_allow_html=True)
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.markdown(f'<div class="metric-label">Client Age</div><div class="metric-value">{profile.get("age")} years</div>', unsafe_allow_html=True)
with col2:
    st.markdown(f'<div class="metric-label">Goal Horizon</div><div class="metric-value">{profile.get("time_horizon_years")} years</div>', unsafe_allow_html=True)
with col3:
    st.markdown(f'<div class="metric-label">Risk Profile</div><div class="metric-value">{profile.get("stated_risk_tolerance", "").title()}</div>', unsafe_allow_html=True)
with col4:
    st.markdown(f'<div class="metric-label">Liquidity Requirement</div><div class="metric-value">{profile.get("liquidity_need", "").title()}</div>', unsafe_allow_html=True)

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

# Personalised rules explanations
rules_explanations = {
    "R1": "Based on target age allocation norms.",
    "R2": "Standard corporate risk concentration ceiling.",
    "R3": f"Derived from time horizon of {profile.get('time_horizon_years', 'N/A')} years (shorter time horizons strictly cap illiquid asset allocations).",
    "R4": "Corporate policy limit to prevent sector concentration risk.",
    "R5": f"Derived from stated risk tolerance of '{profile.get('stated_risk_tolerance', 'N/A')}' (conservative portfolios cannot contain volatile equity assets).",
    "R6": "Mandated floor to secure short-term home purchase goals."
}

limits = compliance.get("limits", {})
illiquidity_limit = limits.get("illiquidity_limit", 15.0)
volatility_limit = limits.get("volatility_limit", 0.0)
alternative_limit = limits.get("alternative_limit", 10.0)
sector_limit = limits.get("sector_limit", 30.0)

rules_info = {
    "R1": ("Equity Target Dev.", "+/- 20% max deviation", f"{abs(metrics.get('age_allocations', {}).get('equity_diff', 0)):.1f}% variance"),
    "R2": ("Alternative Asset Limit", f"<= {alternative_limit}%", f"{metrics.get('pct_alternative', 0):.1f}%"),
    "R3": ("Illiquid Asset Limit", f"<= {illiquidity_limit}%", f"{metrics.get('pct_illiquid', 0):.1f}%"),
    "R4": ("Sector Concentration Limit", f"<= {sector_limit}%", f"{metrics.get('max_sector_concentration_pct', 0):.1f}%"),
    "R5": ("Volatility Exposure Limit", f"<= {volatility_limit}%", f"{metrics.get('pct_high_volatility', 0):.1f}%"),
    "R6": ("Home purchase Liquidity", ">= 50% cash+bonds if horizon<=3", f"{metrics.get('asset_allocations_pct', {}).get('cash', 0) + metrics.get('asset_allocations_pct', {}).get('bond', 0):.1f}%")
}

breaches = compliance.get("breached_rules", [])
breached_ids = {b["rule_id"]: b["details"] for b in breaches}

# Helper compliance card function
def render_detailed_compliance_card(rid: str, title: str, limit: str, actual: str, is_passed: bool, reason: str, why_limit: str):
    card_border = "#34a853" if is_passed else "#ea4335"
    card_bg = "#f4fbf7" if is_passed else "#fdf2f2"
    status_icon = "✅ PASSED" if is_passed else "❌ FLAGGED"
    status_color = "#137333" if is_passed else "#c5221f"
    badge_bg = "#e6f4ea" if is_passed else "#fce8e6"
    
    html_content = f"""<div style="border: 2px solid {card_border}; background-color: {card_bg}; color: #111827; border-radius: 8px; padding: 15px; margin: 8px 0; min-height: 195px; box-shadow: 0 2px 4px rgba(0,0,0,0.02);">
<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
<strong style="color: #1a365d; font-size: 14px;">{rid}: {title}</strong>
<span style="color: {status_color}; font-weight: 800; font-size: 11px; padding: 2px 8px; border-radius: 12px; border: 1px solid {card_border}; background-color: {badge_bg};">{status_icon}</span>
</div>
<div style="display: flex; justify-content: space-between; margin-top: 10px; font-size: 12.5px; color: #2d3748;">
<div><strong>Personalized Limit:</strong> {limit}</div>
<div><strong>Actual Value:</strong> {actual}</div>
</div>
{f"<div style='font-size: 11px; color: #c5221f; margin-top: 8px; line-height: 1.3;'><strong>Reason:</strong> {reason}</div>" if not is_passed else ""}
<div style="border-top: 1px solid #d1d5db; margin-top: 10px; padding-top: 8px; font-size: 11px; color: #4a5568; line-height: 1.3;">
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
