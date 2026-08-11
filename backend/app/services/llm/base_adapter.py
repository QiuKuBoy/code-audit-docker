"""LLM Adapter Base - Unified interface for multiple LLM providers"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional
import json


@dataclass
class ToolCall:
    """A tool call request from the LLM"""
    id: str
    name: str
    arguments: dict


@dataclass
class TokenUsage:
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass
class LLMResponse:
    """Unified response from any LLM provider"""
    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    finish_reason: str = "stop"  # stop / tool_calls / length
    usage: TokenUsage = field(default_factory=TokenUsage)

    @property
    def has_tool_calls(self) -> bool:
        return len(self.tool_calls) > 0

    @property
    def has_final_answer(self) -> bool:
        """Check if the response contains a finalize_finding tool call"""
        return any(tc.name == "finalize_finding" for tc in self.tool_calls)

    @property
    def final_payload(self) -> Optional[dict]:
        """Extract finalize_finding payload if present"""
        for tc in self.tool_calls:
            if tc.name == "finalize_finding":
                return tc.arguments
        return None


class LLMAdapter(ABC):
    """Abstract base for LLM providers"""

    def __init__(self, model: str, api_key: str, base_url: Optional[str] = None):
        self.model = model
        self.api_key = api_key
        self.base_url = base_url

    @abstractmethod
    async def chat(self, messages: list[dict], tools: Optional[list[dict]] = None) -> LLMResponse:
        """Send a chat request and return unified response"""
        pass

    @abstractmethod
    async def summarize(self, messages: list[dict]) -> str:
        """Generate a summary of messages (for auto-compact)"""
        pass
