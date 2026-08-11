"""OpenAI-compatible adapter (also works for DeepSeek)"""

import json
from typing import Optional

from openai import AsyncOpenAI

from ..base_adapter import LLMAdapter, LLMResponse, ToolCall, TokenUsage


class OpenAIAdapter(LLMAdapter):
    """Works with OpenAI, DeepSeek, and any OpenAI-compatible API"""

    def __init__(self, model: str, api_key: str, base_url: Optional[str] = None):
        super().__init__(model, api_key, base_url)
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url) if base_url else AsyncOpenAI(api_key=api_key)

    async def chat(self, messages: list[dict], tools: Optional[list[dict]] = None) -> LLMResponse:
        kwargs = {
            "model": self.model,
            "messages": messages,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        response = await self.client.chat.completions.create(**kwargs)
        choice = response.choices[0]

        tool_calls = []
        if choice.message.tool_calls:
            for tc in choice.message.tool_calls:
                try:
                    args = json.loads(tc.function.arguments) if tc.function.arguments else {}
                except json.JSONDecodeError:
                    args = {"raw": tc.function.arguments}
                tool_calls.append(ToolCall(
                    id=tc.id,
                    name=tc.function.name,
                    arguments=args,
                ))

        usage = TokenUsage(
            input_tokens=response.usage.prompt_tokens if response.usage else 0,
            output_tokens=response.usage.completion_tokens if response.usage else 0,
        )

        return LLMResponse(
            content=choice.message.content or "",
            tool_calls=tool_calls,
            finish_reason=choice.finish_reason or "stop",
            usage=usage,
        )

    async def summarize(self, messages: list[dict]) -> str:
        summary_prompt = (
            "Summarize the following code audit conversation. "
            "Keep: files checked, vulnerabilities found, attack surfaces covered, next steps planned. "
            "Be concise but preserve all technical details."
        )
        msg = [{"role": "system", "content": summary_prompt}] + messages[-20:]
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=msg,
            max_tokens=2000,
        )
        return response.choices[0].message.content or ""
