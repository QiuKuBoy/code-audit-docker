# ============================================================
# CodeAudit — AI 代码安全审计平台
# 多阶段构建: Node 构建前端 → Python 运行后端 (FastAPI 托管 dist)
# ============================================================

# ── Stage 1: Build frontend ──
FROM node:20-alpine AS frontend-builder
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ .
RUN npm run build

# ── Stage 2: Backend runtime ──
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# 系统依赖（git 用于「在线仓库」克隆导入，curl 用于健康检查）
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        git \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# 后端依赖
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

# 后端源码
COPY backend/app /app/backend/app

# 前端构建产物（FastAPI 自动托管 frontend/dist）
COPY --from=frontend-builder /build/dist /app/frontend/dist

# 规则与技能包
COPY rules /app/rules
COPY skills /app/skills

# 运行目录（SQLite / MCP 配置落于此，配合卷持久化）
WORKDIR /app/backend

# 数据卷: 数据库 / 技能包 / MCP 配置
VOLUME ["/data", "/app/skills"]

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -fs http://localhost:8080/api/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
