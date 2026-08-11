"""Anthropic Claude adapter"""

import json
from typing import Optional

from anthropic import AsyncAnthropic

from ..base_adapter import LLMAdapter, LLMResponse, ToolCall, TokenUsage


class AnthropicAdapter(LLMAdapter):
    """Anthropic Claude adapter with native tool use"""

    def __init__(self, model: str, api_key: str, base_url: Optional[str] = None):
        super().__init__(model, api_key, base_url)
        self.client = AsyncAnthropic(api_key=api_key)

    async def chat(self, messages: list[dict], tools: Optional[list[dict]] = None) -> LLMResponse:
        # Convert OpenAI-format messages to Anthropic format
        system_content = ""
        anthropic_messages = []

        for msg in messages:
            if msg["role"] == "system":
                system_content += msg["content"] + "\n"
            elif msg["role"] == "tool":
                # Convert tool result to user message with tool_result
                anthropic_messages.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": msg.get("tool_call_id", ""),
                        "content": msg["content"],
                    }]
                })
            elif msg["role"] == "assistant" and msg.get("tool_calls"):
                # Convert assistant tool_calls to Anthropic format
                content = []
                if msg.get("content"):
                    content.append({"type": "text", "text": msg["content"]})
                for tc in msg["tool_calls"]:
                    content.append({
                        "type": "tool_use",
                        "id": tc["id"],
                        "name": tc["function"]["name"],
                        "input": json.loads(tc["function"]["arguments"]) if isinstance(tc["function"]["arguments"], str) else tc["function"]["arguments"],
                    })
                anthropic_messages.append({"role": "assistant", "content": content})
            else:
                anthropic_messages.append({
                    "role": msg["role"],
                    "content": msg["content"],
                })

        # Convert OpenAI tool format to Anthropic format
        anthropic_tools = []
        if tools:
            for tool in tools:
                fn = tool["function"]
                anthropic_tools.append({
                    "name": fn["name"],
                    "description": fn["description"],
                    "input_schema": fn["parameters"],
                })

        kwargs = {
            "model": self.model,
            "messages": anthropic_messages,
            "max_tokens": 4096,
        }
        if system_content:
            kwargs["system"] = system_content.strip()
        if anthropic_tools:
            kwargs["tools"] = anthropic_tools

        response = await self.client.messages.create(**kwargs)

        content = ""
        tool_calls = []
        for block in response.content:
            if block.type == "text":
                content += block.text
            elif block.type == "tool_use":
                tool_calls.append(ToolCall(
                    id=block.id,
                    name=block.name,
                    arguments=block.input if isinstance(block.input, dict) else json.loads(block.input),
                ))

        usage = TokenUsage(
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )

        finish = "stop"
        if tool_calls:
            finish = "tool_calls"
        elif response.stop_reason == "max_tokens":
            finish = "length"

        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            finish_reason=finish,
            usage=usage,
        )

    async def summarize(self, messages: list[dict]) -> str:
        system = (
            "Summarize the following code audit conversation. "
            "Keep: files checked, vulnerabilities found, attack surfaces covered, next steps. "
            "Be concise but preserve all technical details."
        )
        msg = [{"role": m["role"], "content": m["content"]} for m in messages[-20:] if m["role"] in ("user", "assistant")]
        response = await self.client.messages.create(
            model=self.model,
            system=system,
            messages=msg,
            max_tokens=2000,
        )
        return response.content[0].text if response.content else ""
