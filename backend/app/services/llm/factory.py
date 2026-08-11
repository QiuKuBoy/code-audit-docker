"""LLM Factory - Create adapter by provider name with runtime config"""

from typing import Optional

from app.core.config import settings
from .base_adapter import LLMAdapter
from .adapters.openai_adapter import OpenAIAdapter
from .adapters.anthropic_adapter import AnthropicAdapter
from .adapters.gemini_adapter import GeminiAdapter
from .adapters.baidu_adapter import BaiduAdapter
from .adapters.doubao_adapter import DoubaoAdapter
from .adapters.minimax_adapter import MiniMaxAdapter


# Providers that use the OpenAI-compatible adapter
_OPENAI_COMPATIBLE = {
    "deepseek": (lambda s: s.DEEPSEEK_API_KEY, lambda s: s.DEEPSEEK_BASE_URL, lambda s: s.DEEPSEEK_MODEL),
    "openai":   (lambda s: s.OPENAI_API_KEY,   lambda s: s.OPENAI_BASE_URL,   lambda s: s.OPENAI_MODEL),
    "zhipu":    (lambda s: s.ZHIPU_API_KEY,    lambda s: s.ZHIPU_BASE_URL,    lambda s: s.ZHIPU_MODEL),
    "qwen":     (lambda s: s.QWEN_API_KEY,     lambda s: s.QWEN_BASE_URL,     lambda s: s.QWEN_MODEL),
    "kimi":     (lambda s: s.KIMI_API_KEY,     lambda s: s.KIMI_BASE_URL,     lambda s: s.KIMI_MODEL),
    "siliconflow": (lambda s: s.SILICONFLOW_API_KEY, lambda s: s.SILICONFLOW_BASE_URL, lambda s: s.SILICONFLOW_MODEL),
}

# Native adapters
_NATIVE_ADAPTERS = {
    "anthropic": (AnthropicAdapter, lambda s: s.ANTHROPIC_API_KEY, None, lambda s: s.ANTHROPIC_MODEL),
    "gemini":    (GeminiAdapter,    lambda s: s.GEMINI_API_KEY,    None, lambda s: s.GEMINI_MODEL),
    "baidu":     (BaiduAdapter,     lambda s: s.BAIDU_API_KEY,     None, lambda s: s.BAIDU_MODEL),
    "doubao":    (DoubaoAdapter,    lambda s: s.DOUBAO_API_KEY,    None, lambda s: s.DOUBAO_MODEL),
    "minimax":   (MiniMaxAdapter,   lambda s: s.MINIMAX_API_KEY,   None, lambda s: s.MINIMAX_MODEL),
}


class LLMFactory:
    @staticmethod
    def create(
        provider: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
    ) -> LLMAdapter:
        """
        Create an LLM adapter.

        Priority for api_key / model / base_url:
          1. Explicit runtime argument
          2. settings (.env)
        """
        provider = (provider or settings.DEFAULT_LLM_PROVIDER).lower()

        # ── OpenAI-compatible providers ───────────────────
        if provider in _OPENAI_COMPATIBLE:
            get_key, get_url, get_model = _OPENAI_COMPATIBLE[provider]
            key = api_key or get_key(settings)
            if not key:
                raise ValueError(f"{provider} API Key not provided. Set it in .env or pass via the web UI.")
            return OpenAIAdapter(
                model=model or get_model(settings),
                api_key=key,
                base_url=base_url or get_url(settings),
            )

        # ── Native adapter providers ──────────────────────
        if provider in _NATIVE_ADAPTERS:
            adapter_cls, get_key, _, get_model = _NATIVE_ADAPTERS[provider]
            key = api_key or get_key(settings)
            if not key:
                raise ValueError(f"{provider} API Key not provided. Set it in .env or pass via the web UI.")
            return adapter_cls(
                model=model or get_model(settings),
                api_key=key,
            )

        raise ValueError(
            f"Unknown LLM provider: {provider}. "
            f"Supported: {', '.join(sorted(list(_OPENAI_COMPATIBLE) + list(_NATIVE_ADAPTERS)))}"
        )

    @staticmethod
    def supported_providers() -> list[str]:
        return sorted(list(_OPENAI_COMPATIBLE) + list(_NATIVE_ADAPTERS))
