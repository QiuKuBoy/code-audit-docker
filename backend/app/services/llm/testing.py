"""LLM connectivity testing utilities"""

import asyncio
import time
from datetime import datetime, timezone
from typing import Optional

from app.core.config import settings
from app.services.llm.factory import LLMFactory


async def test_provider_connectivity(
    provider: str,
    api_key: str,
    base_url: str = "",
    model: str = "",
    timeout: float = 20.0,
) -> dict:
    """
    Test if an LLM provider is reachable and the API key is valid.

    Strategy: try to create an adapter and send a tiny chat request.
    Returns dict with keys: ok, status, model, message, latency_ms, tested_at.
    """
    # Determine model to test: explicit > .env default > factory supported
    test_model = model or _get_default_model(provider) or settings.DEEPSEEK_MODEL
    started = time.monotonic()

    def _on_done() -> dict:
        latency = int((time.monotonic() - started) * 1000)
        return {
            "ok": True,
            "status": "ok",
            "model": test_model,
            "message": "API key is valid",
            "latency_ms": latency,
            "tested_at": datetime.now(timezone.utc),
        }

    try:
        adapter = LLMFactory.create(
            provider=provider,
            api_key=api_key,
            model=test_model,
            base_url=base_url,
        )

        # Send a minimal ping message to verify auth + network
        result = await asyncio.wait_for(
            adapter.chat(
                messages=[
                    {"role": "system", "content": "You are a connectivity tester."},
                    {"role": "user", "content": "ping"},
                ],
            ),
            timeout=timeout,
        )

        latency = int((time.monotonic() - started) * 1000)
        content = (result.content or "").strip() if hasattr(result, "content") else ""
        # If the adapter returned any content or any tool calls, we are good
        if content or result.has_tool_calls:
            return {
                "ok": True,
                "status": "ok",
                "model": test_model,
                "message": f"Reachable ({latency}ms)",
                "latency_ms": latency,
                "tested_at": datetime.now(timezone.utc),
            }

        # No content but no exception either — treat as suspicious
        return {
            "ok": False,
            "status": "failed",
            "model": test_model,
            "message": "Empty response from provider",
            "latency_ms": latency,
            "tested_at": datetime.now(timezone.utc),
        }

    except asyncio.TimeoutError:
        latency = int((time.monotonic() - started) * 1000)
        return {
            "ok": False,
            "status": "failed",
            "model": test_model,
            "message": f"Timeout after {int(timeout)}s",
            "latency_ms": latency,
            "tested_at": datetime.now(timezone.utc),
        }
    except ValueError as e:
        latency = int((time.monotonic() - started) * 1000)
        return {
            "ok": False,
            "status": "failed",
            "model": test_model,
            "message": f"Configuration error: {e}",
            "latency_ms": latency,
            "tested_at": datetime.now(timezone.utc),
        }
    except Exception as e:
        latency = int((time.monotonic() - started) * 1000)
        err = str(e)
        # Trim noisy tracebacks
        if len(err) > 500:
            err = err[:500] + "..."
        return {
            "ok": False,
            "status": "failed",
            "model": test_model,
            "message": err or type(e).__name__,
            "latency_ms": latency,
            "tested_at": datetime.now(timezone.utc),
        }


def _get_default_model(provider: str) -> Optional[str]:
    """Resolve the default model name for a provider from settings."""
    mapping = {
        "deepseek": settings.DEEPSEEK_MODEL,
        "openai": settings.OPENAI_MODEL,
        "anthropic": settings.ANTHROPIC_MODEL,
        "gemini": settings.GEMINI_MODEL,
        "baidu": settings.BAIDU_MODEL,
        "doubao": settings.DOUBAO_MODEL,
        "minimax": settings.MINIMAX_MODEL,
        "zhipu": settings.ZHIPU_MODEL,
        "qwen": settings.QWEN_MODEL,
        "kimi": settings.KIMI_MODEL,
        "siliconflow": settings.SILICONFLOW_MODEL,
    }
    return mapping.get(provider.lower())