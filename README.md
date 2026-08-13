# CodeAudit — AI 驱动的代码安全审计平台

> 多阶段 Agent 流水线 · 多智能体协同 · SAST/SCA 引擎扫描 · MCP 知识增强 · 对抗式验证

CodeAudit 是一个开源的 AI 代码安全审计平台，模拟安全专家的思维流程，通过多个智能体（Orchestrator / Recon / Specialist / Verifier / Reporter）协作，实现从代码导入到审计报告的自动化漏洞挖掘与验证。

它不仅仅是一个静态扫描工具——它将 LLM 深度分析与传统 SAST 引擎（Semgrep / SCA / 自定义规则）结合，输出带完整攻击链（Source → Sink）和可执行修复建议的高质量漏洞报告。

## ✨ 核心特性

### 🧠 多智能体协同架构

| 智能体 | 职责 |
|--------|------|
| **Orchestrator 总指挥** | 策略规划、任务分派、结果汇总、误报过滤、报告生成 |
| **Recon 侦察** | 项目结构识别、入口点提取、危险模式扫描（攻击面地图） |
| **Specialist 专精** | 按漏洞类型分派（SQLi / XSS / Auth / RCE / 反序列化...），每 Agent 专注一类 |
| **Verifier 验证** | 对抗式交叉验证（双模型），PoC 校验，剔除误报 |
| **Reporter 报告** | What-Why-How 结构化报告生成 |

- **共享发现总线**：跨 Agent 协同，同类漏洞一次发现、全局标记，避免重复
- **两波编排**：核心专精 Agent 先行，其余 Agent 携带同伴发现继续深挖
- **对抗验证**：独立模型交叉审查每个 finding，REJECTED 直接丢弃

### 🔍 三种审计模式

| 模式 | 流水线 | 适用场景 |
|------|--------|---------|
| ⚡ 快速扫描 Quick | Recon → Scan → Triage → Finalize | 快速覆盖，引擎扫描 + 误报过滤 |
| 🧠 智能审计 Smart | Recon → Finding → Verification → Finalize | 深度挖掘，专精 Agent 分派，适合 0day 研究 |
| 🔳 综合审计 Comprehensive | 全流水线 | 全量审计，引擎 + 深度 + 验证 |

### 🛠 引擎扫描（优雅降级）

- **Semgrep SAST**：OWASP 规则集，命中结果注入 Triage 候选
- **SCA 依赖扫描**：pip-audit（requirements.txt）/ npm audit（package-lock.json）
- **Rule-as-Code**：`rules/` 目录 YAML 规则即写即生效

### 🔌 MCP 知识增强

支持通过 [Model Context Protocol](https://modelcontextprotocol.io/) 连接外部知识库（如 CVE 库、漏洞模式库），审计 Agent 可实时查询已知漏洞参考。支持 **Streamable HTTP** 与 **SSE** 双传输协议。

### 📦 技能包系统（14 个）

按漏洞利用价值/产出效率排序的技能包：RCE、SQLi、认证绕过、反序列化、文件上传、XSS、SSRF、路径遍历、业务逻辑、XXE、竞态条件、硬编码密钥、信息泄露、加密问题。支持自定义技能包上传。

### 📊 报告与导出

- Markdown 报告（按严重级别排序 + CWE/CVSS）
- SARIF 2.1.0（对接 GitHub/GitLab/IDE）
- 中英文报告预览与打印
- 审计对比（两审计交集/差集）

### 🌐 多 LLM 支持（11 家厂商）

DeepSeek / OpenAI / Anthropic / Gemini / Baidu / Doubao / MiniMax / Zhipu / Qwen / Kimi / SiliconFlow，支持双模型交叉验证。

### 🎨 现代化 UI

- 审计流水线可视化（6 阶段动画）
- Agent 编排流程图
- 分页表格（10/20/100 条/页）+ 固定底部状态栏
- 中英文界面切换

## 🚀 快速开始

### 🐳 Docker 一键部署（推荐）

```bash
# 1. 进入项目根目录，准备环境变量
cd code-audit-docker
cp .env.example .env
# 编辑 .env，填入 LLM API Key（也可留空，启动后在网页设置页添加）

# 2. 构建并启动（多阶段构建：Node 构建前端 → Python 运行后端）
docker compose up -d --build

# 3. 访问
# http://localhost:8080
```

**数据持久化**：数据库（SQLite）与自定义技能包分别挂载到命名卷 `codeaudit-data` / `codeaudit-skills`，容器重建不丢数据。

**常用命令**：

```bash
docker compose logs -f          # 查看日志
docker compose restart          # 重启
docker compose down             # 停止（保留数据卷）
docker compose down -v          # 停止并删除数据卷（慎用）
```

**离线/自托管 LLM**：支持任意 OpenAI 兼容接口，在 .env 中配置对应厂商的 `*_BASE_URL` 即可（见 backend/.env.example）。

> 也可不使用 Docker：按下方「本地开发」方式启动。

### 环境要求

- Python 3.11+
- Node.js 20+
- （可选）Semgrep：`pip install semgrep`

### 手动启动

**后端**：

```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
```

**前端**（可选，开发模式）：

```powershell
cd frontend
npm install
npm run dev   # 开发服务器 http://localhost:5173
# 或构建生产版本
npm run build  # 产物在 frontend/dist/，后端会自动托管
```

浏览器打开 <http://localhost:8080> 即可使用。

### 配置 LLM API Key（二选一）

**方式一（推荐）**：启动后打开网页「设置」页添加（Key 加密存储）。

**方式二**：编辑 `backend/.env`：

```bash
cd backend
copy .env.example .env
# 编辑 .env，填入任意一个：
# DEEPSEEK_API_KEY=***
# OPENAI_API_KEY=***
# ANTHROPIC_API_KEY=***
```

### 使用流程

1. **新建项目** — 三种代码来源任选：
   - **上传压缩包**（推荐，Mac / Docker 通用）：选择 .zip 上传，可勾选「创建后立即启动审计」直接开始
   - **在线仓库**：填入 Git 仓库 URL，浅克隆后直接审计
   - **本地路径**：后端运行在本机时，直接输入本地代码路径
2. **启动审计** — 选择模式（Quick/Smart/Comprehensive）、LLM 厂商、模型、最大轮次
3. **实时观察** — 阶段进度条、Agent 编排图、findings 实时入库
4. **导出报告** — Markdown / SARIF / 中英文报告

## 📁 项目结构

```
code-audit-docker/
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI 入口：CORS / 静态托管 dist / 健康检查
│   │   ├── core/
│   │   │   ├── config.py            # Pydantic Settings（11 厂商 / Agent 参数 / 引擎 / 上传·克隆）
│   │   │   ├── crypto.py            # Fernet 加解密（API Key 静态加密，主密钥落 /data/.enc_key）
│   │   │   ├── database.py          # async engine（WAL + busy_timeout）+ session + init_db
│   │   │   └── registry.py          # 工具注册表（ToolRegistry）
│   │   ├── models/
│   │   │   ├── models.py            # ORM：Project / Audit / Finding / AuditLog / APIKey
│   │   │   └── schemas.py           # Pydantic 请求/响应 schema
│   │   ├── api/routes/
│   │   │   ├── projects.py          # 项目 CRUD + /upload（zip 解压）+ /clone（git 浅克隆）
│   │   │   ├── audits.py            # 审计 CRUD / 中止 / 恢复 / 报告 / SARIF / 对比
│   │   │   ├── keys.py              # API Key 管理（加密存储 + 掩码返回）
│   │   │   ├── skills.py            # 技能包 CRUD（含路径穿越防护）
│   │   │   ├── mcp.py               # MCP 服务器配置（运行时落 /data）
│   │   │   ├── llm.py               # 厂商列表 / 模型
│   │   │   └── dashboard.py         # 统计看板
│   │   └── services/
│   │       ├── ingest.py            # 代码导入：zip 解压（含 zip-slip 防护）/ git clone
│   │       ├── llm/
│   │       │   ├── base_adapter.py  # LLMAdapter 抽象（chat / summarize）
│   │       │   ├── factory.py       # 厂商工厂
│   │       │   ├── testing.py       # StubLLM（测试用）
│   │       │   └── adapters/        # 11 家厂商适配器（OpenAI 兼容类复用 openai_adapter）
│   │       └── agent/
│   │           ├── service.py       # 审计工作流编排（_run_audit_task）
│   │           ├── orchestrator.py  # 并行分块编排（目录分块 + 去重合并）
│   │           ├── specialist_orchestrator.py  # 专精 Agent 分派
│   │           ├── core/            # loop / state / memory / registry / specialists
│   │           ├── tools/           # agent_tools（read/grep/scan/finalize）+ mcp_tools（MCP bridge）
│   │           ├── skills/          # 技能包匹配 manager
│   │           ├── scanners/        # engine（Semgrep / SCA / 自定义规则，优雅降级）
│   │           ├── rules/           # YAML 规则加载
│   │           ├── verification/    # PoC 沙箱（静态 AST 校验 + 可选执行）
│   │           ├── export/          # SARIF 2.1.0 导出
│   │           └── prompts/         # 阶段感知 system prompt
│   └── requirements.txt
├── frontend/                      # React 18 + TypeScript + TailwindCSS + Vite
│   └── src/
│       ├── pages/                 # Dashboard / Projects / ProjectDetail / AuditDetail / Skills / MCP / Settings
│       ├── services/api.ts        # 全部 API 调用封装
│       ├── types/index.ts         # TS 接口（与 Pydantic schema 对齐）
│       └── i18n/index.tsx         # 中英文案
├── rules/                         # Rule-as-Code YAML 规则（custom_rules.yml）
├── skills/                        # 14 个漏洞类型技能包（每个含 SKILL.md）
├── docs/                          # 完整文档：USER_GUIDE / ARCHITECTURE / DEVELOPER
├── Dockerfile / docker-compose.yml
├── .env.example / backend/.env.example
├── LICENSE / README.md / README.en.md
```

> 构建产物 `frontend/dist/` 由后端静态托管；数据库、上传代码、技能包、运行时配置均落在 Docker 卷 `/data`（命名卷 `codeaudit-data`）与 `codeaudit-skills`，容器重建不丢。


## 📚 文档

| 文档 | 内容 |
|------|------|
| [docs/USER_GUIDE.md](docs/USER_GUIDE.md) | 用户手册：安装、启动、配置、完整使用流程 |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | 架构文档：模块职责、数据流、阶段状态机 |
| [docs/DEVELOPER.md](docs/DEVELOPER.md) | 开发者指南：扩展规则/技能/LLM/引擎/API |

## 🔒 安全设计

- API Key 静态加密存储（Fernet），接口返回掩码
- PoC 沙箱验证（可选 Docker 隔离执行）
- 报告导出不含明文密钥
- 路径穿越防护（`_safe_path` 边界感知）

## 📄 License

[MIT](LICENSE)
