# 开发者指南（Developer Guide）

本文档面向**开发者**：如何扩展规则、技能、LLM 适配器、引擎、API 与前端。

---

## 1. 开发环境

```bash
# 推荐用 Docker 启动（全平台一致）：
cd code-audit-docker
docker compose up -d --build

# 或本地开发模式（不依赖 Docker）：
# 后端
cd backend
python -m venv .venv
source .venv/bin/activate        # Windows: .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8080

# 前端（另一终端）
cd frontend
npm install
npm run dev   # http://localhost:5173（dev server 代理 /api 到 8080）
```

> 项目根目录名为 `code-audit-docker`（非 `code-audit`）。Docker 模式环境变量读根目录 `.env`；本地模式读 `backend/.env`。

## 2. 代码结构速查

```
backend/app/
├── main.py                    # 入口（含 CORS、静态托管 dist、健康检查）
├── core/
│   ├── config.py              # Settings（11 厂商、Agent 参数、引擎、上传·克隆）
│   ├── crypto.py              # Fernet 加解密（API Key 静态加密，主密钥落 /data/.enc_key）
│   ├── database.py            # async engine（WAL）+ session + init_db
│   └── registry.py            # 工具注册表
├── models/
│   ├── models.py              # ORM：Project/Audit/Finding/AuditLog/APIKey
│   └── schemas.py             # Pydantic：响应/请求 schema
├── api/routes/
│   ├── projects.py / audits.py / keys.py / dashboard.py / mcp.py / llm.py
├── services/
│   ├── ingest.py              # 代码导入：zip 解压 + git clone
│   ├── llm/                   # base_adapter + adapters/ + factory + testing(StubLLM)
│   └── agent/
│       ├── core/              # loop.py / state.py / memory.py / registry.py / specialists.py
│       ├── tools/             # agent_tools.py + mcp_tools.py（MCP bridge）
│       ├── skills/manager.py
│       ├── scanners/engine.py
│       ├── rules/loader.py
│       ├── verification/sandbox.py
│       ├── export/sarif.py
│       ├── prompts/system_prompt.py
│       ├── orchestrator.py
│       ├── specialist_orchestrator.py
│       └── service.py
frontend/src/
├── pages/                     # Dashboard / Projects / ProjectDetail / AuditDetail / Skills / MCP / Settings
├── services/api.ts            # 全部 API 调用
├── types/index.ts             # TS 接口（与 Pydantic schema 对齐）
└── i18n/index.tsx             # zh / en 文案
```

## 3. 如何扩展

### 3.1 新增自定义检测规则（最简单）

在 `rules/` 下新建 YAML 或编辑 `rules/custom_rules.yml`：

```yaml
- id: MY-CUSTOM-RULE
  type: dangerous-function
  severity: HIGH
  languages: [python]
  patterns:
    - pickle.loads(
  message: "Unsafe deserialization via pickle"
  cwe: "CWE-502"
  exclude: ["**/tests/**"]
```

规则自动被 `rules/loader.py` 加载，`run_custom_rules` 工具与引擎扫描都会执行。
修改后无需重启（每次加载重新读盘）。

### 3.2 新增技能包（SKILL.md）

在 `skills/<name>/SKILL.md` 创建：

```markdown
---
name: my_skill
description: 技能简介（用于匹配判断）
languages: [python, java]
keywords: [xxe, xml]
---

# My Skill

## 方法论
...

## 常见模式
- 模式 1：...
- 模式 2：...

## 绕过技巧
...

## Checklist
- [ ] ...
```

匹配逻辑（`skills/manager.py`）：
- `always` 字段标记的技能无条件注入（如 auth_bypass / hardcoded_secret / info_disclosure / sqli）
- 其余按 languages 关键词与技术栈匹配
- briefing 注入 system prompt；`load_skill` 工具按需读全文

### 3.3 新增 LLM 厂商

1. **适配器**：在 `services/llm/adapters/` 新建 `xxx_adapter.py`，继承 `LLMAdapter`：
   ```python
   class XxxAdapter(LLMAdapter):
       async def chat(self, messages, tools=None) -> LLMResponse: ...
       async def summarize(self, messages) -> str: ...
   ```
   OpenAI 兼容的厂商可直接复用 `OpenAIAdapter`（改 base_url）。
2. **注册**：`core/config.py` 的 PROVIDERS 字典加条目；`factory.py` 加分支。
3. **前端**：`frontend/src` 厂商下拉列表由 `/api/llm/providers` 动态获取，无需改前端。

### 3.4 新增 Agent 工具

1. 在 `tools/agent_tools.py` 写 handler 函数（async，入参 dict，返回 str/JSON）
2. 在 `service.py::_run_audit_task` 注册：
   ```python
   registry.register(
       name="my_tool",
       description="...",
       parameters={...openai function schema...},
       handler=my_handler,
   )
   ```
3. 工具描述自动注入 LLM tools；LLM 调用后结果追加到消息历史

### 3.5 新增引擎

在 `scanners/engine.py` 加方法：
```python
async def run_my_scanner(self, project_path) -> list[ScanCandidate]:
    if not shutil.which("my-scanner"):
        self.status["my_scanner"] = "skipped"
        return []
    ...
```
保持**优雅降级**约定：CLI 缺失返回空列表并标记 skipped，绝不抛异常。

### 3.6 新增 API 端点

1. `api/routes/xxx.py` 新建 router（或加到现有路由）
2. `main.py` include_router
3. 如需响应 schema：`models/schemas.py` 定义 Pydantic 模型
4. 前端 `services/api.ts` 加调用方法 + `types/index.ts` 加接口
5. 若涉及审计新字段：`models/models.py` 加列 + `schemas.py` + 前端类型 + 报告/SARIF

> ⚠️ SQLite 已存在的表不会自动加列（`create_all` 只建新表）。加字段后需手动迁移：
> ```sql
> ALTER TABLE audits ADD COLUMN stage TEXT DEFAULT 'recon';
> ALTER TABLE audits ADD COLUMN stages_completed TEXT DEFAULT '[]';
> ALTER TABLE audits ADD COLUMN scan_candidates_count INTEGER DEFAULT 0;
> ALTER TABLE findings ADD COLUMN cwe TEXT DEFAULT '';
> ALTER TABLE findings ADD COLUMN poc_verified BOOLEAN;
> ```

### 3.7 修改 Agent 行为

- **终止/守卫逻辑**：`core/loop.py` 的 `_coverage_check` / `_scan_check` / finish 分支
- **提示词**：`prompts/system_prompt.py`（方法论 5 步、模式说明、候选利用指引）
- **压缩策略**：`core/memory.py`（阈值、预算、滑窗大小）
- **阶段流转**：`core/state.py::mark_stage` + `loop.py` 各阶段入口

## 4. 测试

### 4.1 快速自检脚本（对照实现）

| 测试点 | 方式 |
|--------|------|
| 模块编译 | `python -m compileall app` 或逐个 `py_compile` |
| 引擎/规则/SARIF/沙箱 | 直接调用模块函数断言 |
| 工具层 | 构造 fake project 目录，调 handler 断言 |
| 循环层 | StubLLM（实现 LLMAdapter，固定返回序列）驱动 ReActLoop |
| 服务层 E2E | 建真实 Project → `_run_audit_task` → 查 DB 断言 status/findings/stage |

> ⚠️ StubLLM 构造签名必须匹配 `LLMFactory.create(**kw)` 的传参
> （model/api_key/base_url），否则出现误导性 failed。

### 4.2 前端

```bash
cd frontend
npx tsc --noEmit        # TS 类型检查
npm run build           # 生产构建
```

### 4.3 端到端验证清单（改完必跑）

1. `python -X utf8 -m compileall app` 全绿
2. 启动服务后：`/` `/docs` `/api/projects` `/api/audits` `/api/keys` 全 200
3. 建项目 + 启动审计（stub 或真实 LLM）→ 观察 stage 推进到 finalize
4. findings 落库 + `GET /api/audits/{id}/report` + `/sarif` 正常
5. `npm run build` 通过（前端改动时）

## 5. Git 规范

仓库已 `git init`（基线 `6b2330b`），改造里程碑提交：

```
6b2330b baseline: original code-audit before upgrade
34361aa upgrade: multi-stage pipeline, SAST/SCA engines, rule-as-code, SARIF, skills matching, coverage termination, path safety, masked keys
bd2d3c9 add: multi-agent orchestrator (AutoCVE-style parallel chunked audit with merged dedup)
00a504a security: encrypt API keys at rest (Fernet + legacy compat), mask on API, docs
```

约定：
- 改完一批功能即 commit（方便回滚），勿攒大量改动一次提交
- 提交信息格式：`<type>: <summary>`（type: upgrade/add/fix/security/chore/docs）
- 重要改动先备份或确认 git 状态干净
- 提交前确认 `.env`、`*.db`、`.enc_key` 等敏感文件已被 `.gitignore` 忽略，不进入版本库

## 6. 备份与回滚

```bash
# 全量备份（改造前快照）
cp -r code-audit-docker code-audit-docker_backup_<date>

# Docker 数据卷备份
docker run --rm -v codeaudit-data:/data -v "$(pwd)":/backup busybox \
  tar czf /backup/codeaudit-data-<date>.tar.gz -C /data .

# 回滚到某提交
git log --oneline
git checkout <commit> -- <path>   # 单文件
git reset --hard <commit>         # 全量回滚（谨慎）
```

## 7. 常见开发坑

| 坑 | 说明 |
|----|------|
| Docker 中环境变量不生效 | 确认 `docker-compose.yml` 已 `environment:` 注入，且根目录 `.env` 已 `cp .env.example .env` |
| curl 验证状态码 | 用 `curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/api/health` |
| 中文环境脚本乱码 | 脚本文件保存为 UTF-8（无 BOM）；跨平台优先用 `bash` 而非 PowerShell |
| aiosqlite + SQLite 加列 | create_all 不改旧表，需手动 ALTER TABLE |
| tool_calls 与 role=tool 不配对 | 会 400；memory 层 `_sanitize_tool_pairs` 兜底，但测试中注意 |
| 引擎扫描阻塞事件循环 | 必须 `asyncio.to_thread` 包装（grep / Semgrep / PoC 均如此） |
| Mac / 容器访问不到代码 | 用「上传压缩包」或「Git 仓库」，不要依赖「本地路径」（容器内无宿主机路径） |

## 8. 安全审计（对平台自身）

平台自身安全特性：
- API Key Fernet 加密 + 掩码返回
- `_safe_path` 前缀边界防护
- 沙箱验证受限执行（禁 shell/网络/危险库）
- 报告导出不含明文密钥

已知待改进（如需加固）：
- 后端 API 无鉴权（本地工具场景可接受；公网部署需加认证）
- SQLite 无加密（数据库文件属敏感资产）
- 审计目标为任意本地路径（需确保使用者在授权环境运行）
