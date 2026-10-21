"""Deterministic stand-in for Gemini so the full nine-agent pipeline runs offline.

It reads which tools the current agent has (from the request) and drives them in
order: call the agent's first tool; if that tool has a paired ``save_*`` tool,
pass its output straight to the save tool; then end the turn with a short note.
It never writes content of its own, so in offline mode every word in the final
summary comes from ``app.engine``.
"""

from __future__ import annotations

import re
from collections.abc import AsyncGenerator

from google.adk.models import BaseLlm
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.genai import types

# fetch tool -> (save tool, argument name the save tool expects)
SAVE_AFTER = {
    "get_client": ("save_client_profile", "profile_json"),
    "get_strategy_baseline": ("save_planning_strategy", "strategy_json"),
    "draft_advisor_summary": ("save_final_summary", "summary_text"),
}

CLIENT_ID = re.compile(r"\bC\d{3,5}\b")


_NO_TOKENS = types.GenerateContentResponseUsageMetadata(prompt_token_count=0, candidates_token_count=0, total_token_count=0)


def _call(name: str, args: dict) -> LlmResponse:
    return LlmResponse(usage_metadata=_NO_TOKENS, content=types.Content(role="model", parts=[
        types.Part(function_call=types.FunctionCall(name=name, args=args))
    ]))


def _say(text: str) -> LlmResponse:
    return LlmResponse(usage_metadata=_NO_TOKENS, content=types.Content(role="model", parts=[types.Part(text=text)]))


def _client_id(request: LlmRequest) -> str | None:
    for content in reversed(request.contents):
        for part in content.parts or []:
            match = part.text and CLIENT_ID.search(part.text)
            if match:
                return match.group(0)
    return None


class OfflineLlm(BaseLlm):
    model: str = "offline-deterministic"

    async def generate_content_async(self, llm_request: LlmRequest, stream: bool = False) -> AsyncGenerator[LlmResponse, None]:
        tools = list(llm_request.tools_dict)
        last = llm_request.contents[-1] if llm_request.contents else None
        response = next((p.function_response for p in (last.parts or []) if p.function_response), None) if last else None

        if response is None:
            first = next(t for t in tools if not t.startswith("save_"))
            args = {}
            if first == "get_client":
                client_id = _client_id(llm_request)
                if not client_id:
                    yield _say("No client ID found in the request.")
                    return
                args = {"client_id": client_id}
            yield _call(first, args)
            return

        payload = (response.response or {}).get("result", "")
        if response.name in SAVE_AFTER and not str(payload).startswith("Error"):
            save_tool, arg = SAVE_AFTER[response.name]
            yield _call(save_tool, {arg: payload})
            return
        yield _say(str(payload))
