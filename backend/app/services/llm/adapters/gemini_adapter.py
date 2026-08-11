"""Google Gemini adapter (native API)"""

import json
from typing import Optional

import httpx

from ..base_adapter import LLMAdapter, LLMResponse, ToolCall, TokenUsage


class GeminiAdapter(LLMAdapter):
    """Google Gemini native REST API adapter"""

    BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

    def __init__(self, model: str, api_key: str, base_url: Optional[str] = None):
        super().__init__(model, api_key, base_url or self.BASE_URL)

    async def chat(self, messages: list[dict], tools: Optional[list[dict]] = None) -> LLMResponse:
        # Convert to Gemini format
        system_instruction = None
        contents = []
        for msg in messages:
            role = msg["role"]
            if role == "system":
                system_instruction = {"parts": [{"text": msg["content"]}]}
                continue
            gemini_role = "user" if role in ("user", "tool") else "model"
            content = msg.get("content", "")
            # Handle tool results
            if role == "tool":
                contents.append({
                    "role": "user",
                    "parts": [{"text": f"Tool result: {content}"}]
                })
                continue
            # Handle assistant with tool_calls
            if role == "assistant" and msg.get("tool_calls"):
                parts = []
                if content:
                    parts.append({"text": content})
                for tc in msg["tool_calls"]:
                    parts.append({
                        "functionCall": {
                            "name": tc["function"]["name"],
                            "args": json.loads(tc["function"]["arguments"]) if isinstance(tc["function"]["arguments"], str) else tc["function"]["arguments"],
                        }
                    })
                contents.append({"role": "model", "parts": parts})
                continue
            contents.append({"role": gemini_role, "parts": [{"text": content}]})

        # Convert tools to Gemini format
        gemini_tools = None
        if tools:
            declarations = []
            for tool in tools:
                fn = tool["function"]
                declarations.append({
                    "name": fn["name"],
                    "description": fn["description"],
                    "parameters": fn["parameters"],
                })
            gemini_tools = [{"function_declarations": declarations}]

        body: dict = {"contents": contents}
        if system_instruction:
            body["systemInstruction"] = system_instruction
        if gemini_tools:
            body["tools"] = gemini_tools

        url = f"{self.base_url}/models/{self.model}:generateContent?key={self.api_key}"
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(url, json=body)
            resp.raise_for_status()
            data = resp.json()

        candidates = data.get("candidates", [])
        if not candidates:
            return LLMResponse(content="", finish_reason="stop")

        candidate = candidates[0]
        parts = candidate.get("content", {}).get("parts", [])
        content = ""
        tool_calls = []
        for part in parts:
            if "text" in part:
                content += part["text"]
            elif "functionCall" in part:
                fc = part["functionCall"]
                tool_calls.append(ToolCall(
                    id=fc["name"],
                    name=fc["name"],
                    arguments=fc.get("args", {}),
                ))

        finish = "tool_calls" if tool_calls else "stop"
        if candidate.get("finishReason") == "MAX_TOKENS":
            finish = "length"

        usage_meta = data.get("usageMetadata", {})
        usage = TokenUsage(
            input_tokens=usage_meta.get("promptTokenCount", 0),
            output_tokens=usage_meta.get("candidatesTokenCount", 0),
        )

        return LLMResponse(content=content, tool_calls=tool_calls, finish_reason=finish, usage=usage)

    async def summarize(self, messages: list[dict]) -> str:
        msg = [{"role": "user", "content": "Summarize this audit conversation concisely:\n" +
                "\n".join(m.get("content", "") for m in messages[-20:] if m["role"] in ("user", "assistant"))}]
        resp = await self.chat(msg)
        return resp.content
