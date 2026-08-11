"""Code Audit - Configuration"""

from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment / .env file"""

    # App
    APP_NAME: str = "Code Audit"
    APP_VERSION: str = "1.1.0"
    DEBUG: bool = False

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./code_audit.db"

    # ── LLM Providers (2026-08 latest models) ────────────────────────────
    # Each provider has: API_KEY, BASE_URL (optional), MODEL
    # API keys are optional — can be entered per-audit in the web UI

    # DeepSeek (V4 series — V4-Flash free, V4-Pro flagship)
    DEEPSEEK_API_KEY: Optional[str] = None
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com/v1"
    DEEPSEEK_MODEL: str = "deepseek-v4-flash"

    # OpenAI (GPT-5.5 — latest from-zero retrain)
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    OPENAI_MODEL: str = "gpt-5.5"

    # Anthropic (Claude Fable 5 — strongest; Opus 4.8 — balanced)
    ANTHROPIC_API_KEY: Optional[str] = None
    ANTHROPIC_MODEL: str = "claude-fable-5"

    # Google Gemini (3.5 Flash — latest I/O 2026)
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_MODEL: str = "gemini-3.5-flash"

    # Baidu Wenxin (ERNIE 4.5 — latest)
    BAIDU_API_KEY: Optional[str] = None
    BAIDU_MODEL: str = "ernie-4.5-8k-latest"

    # ByteDance Doubao (Seed 2.0 Pro — SuperCLUE #1 domestic)
    DOUBAO_API_KEY: Optional[str] = None
    DOUBAO_MODEL: str = "doubao-seed-2.0-pro-256k-250628"

    # MiniMax (M2.5 — SWE-Bench 80.2%)
    MINIMAX_API_KEY: Optional[str] = None
    MINIMAX_MODEL: str = "MiniMax-M2.5"

    # Zhipu GLM (GLM-5.2 — 744B MoE, open-source #1)
    ZHIPU_API_KEY: Optional[str] = None
    ZHIPU_BASE_URL: str = "https://open.bigmodel.cn/api/paas/v4"
    ZHIPU_MODEL: str = "glm-5.2"

    # Alibaba Tongyi Qianwen (Qwen3.8-Max — 2.4T flagship)
    QWEN_API_KEY: Optional[str] = None
    QWEN_BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    QWEN_MODEL: str = "qwen3.8-max-preview"

    # Moonshot Kimi (K3 — 2.8T, world's largest open-source)
    KIMI_API_KEY: Optional[str] = None
    KIMI_BASE_URL: str = "https://api.moonshot.cn/v1"
    KIMI_MODEL: str = "kimi-k3"

    # SiliconFlow (aggregator — many models via one API)
    SILICONFLOW_API_KEY: Optional[str] = None
    SILICONFLOW_BASE_URL: str = "https://api.siliconflow.cn/v1"
    SILICONFLOW_MODEL: str = "Qwen/Qwen3.8-Max-Preview"

    # Default LLM provider
    DEFAULT_LLM_PROVIDER: str = "deepseek"

    # Agent
    MAX_TURNS: int = 50
    MAX_TOOL_CALLS: int = 200
    CONTEXT_WINDOW_TOKENS: int = 128000
    COMPRESS_THRESHOLD: float = 0.6
    TOOL_RESULT_BUDGET: int = 8000

    # Sandbox (PoC verification)
    SANDBOX_ENABLED: bool = False
    SANDBOX_TIMEOUT: int = 15          # seconds per PoC execution
    SANDBOX_MAX_OUTPUT: int = 4000     # max chars captured from PoC output

    # Scan engines (each gracefully degrades if the CLI is not installed)
    SEMGREP_ENABLED: bool = True
    SEMGREP_CONFIG: str = "p/owasp-top-ten"   # or a local rules dir
    SEMGREP_TIMEOUT: int = 120
    SCA_ENABLED: bool = True
    SCA_TIMEOUT: int = 120

    # Candidate list injected into LLM context from engine scans
    MAX_SCAN_CANDIDATES: int = 60       # cap candidates fed to the LLM per audit
    MAX_SCAN_CANDIDATES_QUICK: int = 30

    # ── MCP (Model Context Protocol) Servers ────────────────────────────
    # Connect to external knowledge bases for vulnerability lookup during audits.
    # Configured at runtime via the web UI or mcp_servers.json file.
    MCP_SERVERS: dict = {}

    # Rule-as-code (custom YAML detection rules)
    RULES_DIR: str = "rules"            # resolved relative to project root of code-audit

    # Coverage-driven termination
    COVERAGE_MIN_FILES: int = 1         # minimum files that must be read before finish_audit is allowed
    COVERAGE_REQUIRE_SCAN: bool = True  # require at least one engine scan before finish in comprehensive mode

    # Audit modes: quick (enhanced-scan) / smart (finding deep-dive) / comprehensive (scan+deep-dive)
    MODE_META: dict = {
        "quick": {"label": "增强扫描", "stages": ["recon", "scan", "triage", "finalize"]},
        "smart": {"label": "智能审计", "stages": ["recon", "finding", "verification", "finalize"]},
        "comprehensive": {"label": "综合审计", "stages": ["recon", "scan", "triage", "finding", "verification", "finalize"]},
    }

    # CORS
    CORS_ORIGINS: list = ["http://localhost:5173", "http://localhost:3000", "http://localhost:8080"]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
