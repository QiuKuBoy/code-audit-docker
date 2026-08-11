"""LLM Config API - Tell frontend which providers have keys configured in DB"""

from fastapi import APIRouter
from sqlalchemy import select

from app.core.config import settings
from app.core.database import async_session
from app.models.models import APIKey
from app.models.schemas import LLMConfigInfo

router = APIRouter(prefix="/api/llm", tags=["llm"])

# ── Provider registry: (provider_id, display_name, model_default) ──
_PROVIDERS = [
    ("deepseek",    "DeepSeek 深度求索",     settings.DEEPSEEK_MODEL),
    ("openai",      "OpenAI GPT",           settings.OPENAI_MODEL),
    ("anthropic",   "Anthropic Claude",     settings.ANTHROPIC_MODEL),
    ("gemini",      "Google Gemini",        settings.GEMINI_MODEL),
    ("baidu",       "百度文心 ERNIE",        settings.BAIDU_MODEL),
    ("doubao",      "字节豆包 Doubao",       settings.DOUBAO_MODEL),
    ("minimax",     "MiniMax",              settings.MINIMAX_MODEL),
    ("zhipu",       "智谱 GLM",             settings.ZHIPU_MODEL),
    ("qwen",        "通义千问 Qwen",         settings.QWEN_MODEL),
    ("kimi",        "月之暗面 Kimi",         settings.KIMI_MODEL),
    ("siliconflow", "硅基流动 SiliconFlow",  settings.SILICONFLOW_MODEL),
]


@router.get("/providers", response_model=list[LLMConfigInfo])
async def list_providers():
    """List all supported LLM providers and their DB configuration status.

    `configured` is now based on whether at least one key exists in api_keys
    table for this provider. .env is no longer consulted.
    """
    # Batch query: get all configured providers in one go
    configured_set = set()
    async with async_session() as db:
        result = await db.execute(select(APIKey.provider).distinct())
        configured_set = {row[0] for row in result.fetchall() if row[0]}

    out = []
    for provider_id, _display, default_model in _PROVIDERS:
        out.append(LLMConfigInfo(
            provider=provider_id,
            configured=provider_id.lower() in configured_set,
            default_model=default_model,
        ))
    return out