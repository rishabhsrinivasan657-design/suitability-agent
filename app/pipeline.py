"""Run the nine-agent review and capture a step-by-step trace for the UI and report."""

from __future__ import annotations

import asyncio
import json
import os
import time
import uuid
from dataclasses import dataclass, field

from google.adk.runners import InMemoryRunner
from google.genai import types

from app.agent import AGENT_TITLES, build_pipeline
from app.offline_llm import OfflineLlm

APP_NAME = "shieldwealth"
STATE_KEYS = (
    "client_profile", "market_context", "financial_stability_profile", "portfolio_metrics",
    "holdings", "risk_flags", "compliance_result", "rebalance_plan", "planning_strategy",
    "product_research_result", "final_summary",
)


@dataclass
class ReviewResult:
    state: dict
    trace: list[dict] = field(default_factory=list)
    mode: str = "offline"
    seconds: float = 0.0

    @property
    def complete(self) -> bool:
        return all(k in self.state for k in STATE_KEYS)

    @property
    def errors(self) -> list[dict]:
        return [t for t in self.trace if t["kind"] == "tool_result" and str(t["detail"]).startswith("Error")]


def gemini_available() -> bool:
    return bool(os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY"))


def _short(value: object, limit: int = 220) -> str:
    if isinstance(value, str) and value.startswith("{"):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            pass
    if isinstance(value, dict) and value:
        # Tool payloads are big JSON blobs; show the gist rather than a truncated dump.
        for key in ("headline", "recommendation", "name"):
            if isinstance(value.get(key), str):
                return _short(value[key], limit)
        return "{" + ", ".join(list(value)[:6]) + ("…" if len(value) > 6 else "") + "}"
    text = value if isinstance(value, str) else json.dumps(value, default=str, ensure_ascii=False)
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _args(args: dict) -> str:
    return ", ".join(f"{k}={v}" if len(str(v)) <= 40 else f"{k}=<{len(str(v)):,} chars>" for k, v in args.items())


async def run_review_async(client_id: str, *, mode: str = "offline", market_scenario: str = "baseline",
                           staged_client: dict | None = None, model=None) -> ReviewResult:
    """Run the pipeline. ``model`` overrides the model picked by ``mode`` (used by tests)."""
    model = model or (OfflineLlm() if mode == "offline" else None)
    runner = InMemoryRunner(agent=build_pipeline(model), app_name=APP_NAME)
    initial = {"market_scenario": market_scenario}
    if staged_client:
        initial["staged_client"] = staged_client
    session = await runner.session_service.create_session(
        app_name=APP_NAME, user_id="advisor", session_id=str(uuid.uuid4()), state=initial,
    )
    message = types.Content(role="user", parts=[types.Part(text=f"Run a suitability review for client {client_id}.")])

    trace: list[dict] = []
    start = time.perf_counter()
    async for event in runner.run_async(user_id="advisor", session_id=session.id, new_message=message):
        agent = AGENT_TITLES.get(event.author, event.author)
        elapsed = round(time.perf_counter() - start, 3)
        for part in (event.content.parts if event.content else None) or []:
            if part.function_call:
                trace.append({"agent": agent, "kind": "tool_call", "name": part.function_call.name,
                              "detail": _args(part.function_call.args or {}), "t": elapsed})
            elif part.function_response:
                result = (part.function_response.response or {}).get("result", part.function_response.response)
                trace.append({"agent": agent, "kind": "tool_result", "name": part.function_response.name,
                              "detail": _short(result), "t": elapsed})
            elif part.text and not event.partial:
                text = part.text.strip()
                if trace and trace[-1]["agent"] == agent and trace[-1]["detail"] == _short(text):
                    continue  # agent just echoed its tool result
                trace.append({"agent": agent, "kind": "message", "name": "", "detail": _short(text), "t": elapsed})

    final = await runner.session_service.get_session(app_name=APP_NAME, user_id="advisor", session_id=session.id)
    state = {k: v for k, v in final.state.items() if not k.startswith("_")}
    return ReviewResult(state=state, trace=trace, mode=mode, seconds=round(time.perf_counter() - start, 2))


def run_review(client_id: str, **kwargs) -> ReviewResult:
    return asyncio.run(run_review_async(client_id, **kwargs))
