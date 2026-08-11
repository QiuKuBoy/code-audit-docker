"""MiniMax adapter"""

import json
from typing import Optional

import httpx

from ..base_adapter import LLMAdapter, LLMResponse, ToolCall, TokenUsage


class MiniMaxAdapter(LLMAdapter):
    """MiniMax adapter via OpenAI-compatible API"""

    BASE_URL = "https://api.minimaxi.com/v1"

    def __init__(self, model: str, api_key: str, base_url: Optional[str] = None):
        super().__init__(model, api_key, base_url or self.BASE_URL)

    async def chat(self, messages: list[dict], tools: Optional[list[dict]] = None) -> LLMResponse:
        body: dict = {
            "model": self.model,
            "messages": [],
        }

        for msg in messages:
            role = msg["role"]
            if role == "system":
                body["messages"].append({"role": "system", "content": msg["content"]})
            elif role == "tool":
                body["messages"].append({
                    "role": "tool",
                    "tool_call_id": msg.get("tool_call_id", ""),
                    "content": msg["content"],
                })
            elif role == "assistant" and msg.get("tool_calls"):
                body["messages"].append({
                    "role": "assistant",
                    "content": msg.get("content", ""),
                    "tool_calls": msg["tool_calls"],
                })
            else:
                body["messages"].append({"role": role, "content": msg["content"]})

        if tools:
            body["tools"] = tools
            body["tool_choice"] = "auto"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        url = f"{self.base_url}/chat/completions"
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(url, json=body, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        choice = data.get("choices", [{}])[0]
        msg_obj = choice.get("message", {})

        tool_calls = []
        for tc in msg_obj.get("tool_calls", []):
            func = tc.get("function", {})
            try:
                args = json.loads(func.get("arguments", "{}")) if func.get("arguments") else {}
            except json.JSONDecodeError:
                args = {"raw": func.get("arguments", "")}
            tool_calls.append(ToolCall(
                id=tc.get("id", ""),
                name=func.get("name", ""),
                arguments=args,
            ))

        usage_data = data.get("usage", {})
        usage = TokenUsage(
            input_tokens=usage_data.get("prompt_tokens", 0),
            output_tokens=usage_data.get("completion_tokens", 0),
        )

        finish = "tool_calls" if tool_calls else choice.get("finish_reason", "stop")

        return LLMResponse(
            content=msg_obj.get("content", ""),
            tool_calls=tool_calls,
            finish_reason=finish,
            usage=usage,
        )

    async def summarize(self, messages: list[dict]) -> str:
        msg = [{"role": "user", "content": "Summarize this audit conversation concisely:\n" +
                "\n".join(m.get("content", "") for m in messages[-20:] if m["role"] in ("user", "assistant"))}]
        resp = await self.chat(msg)
        return resp.content
