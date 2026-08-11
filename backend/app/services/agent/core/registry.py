"""Tool Registry - Register and describe available tools for the LLM"""

from typing import Callable, Optional
import json


class ToolDefinition:
    def __init__(self, name: str, description: str, parameters: dict, handler: Callable):
        self.name = name
        self.description = description
        self.parameters = parameters
        self.handler = handler

    def to_openai_format(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            }
        }


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, name: str, description: str, parameters: dict, handler: Callable):
        self._tools[name] = ToolDefinition(name, description, parameters, handler)

    def get(self, name: str) -> Optional[ToolDefinition]:
        return self._tools.get(name)

    def describe(self) -> list[dict]:
        """Return tool definitions in OpenAI format"""
        return [t.to_openai_format() for t in self._tools.values()]

    def list_names(self) -> list[str]:
        return list(self._tools.keys())
