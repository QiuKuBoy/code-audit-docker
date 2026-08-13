# 架构文档（Architecture）

本文档面向**开发者与维护者**：系统模块职责、数据流、阶段状态机、关键实现细节。

---

## 1. 总体架构

```
┌─────────────────────────────────────────────────────────┐
│                    Frontend (React+TS+Vite)              │
│   Dashboard │ Projects │ AuditDetail(阶段进度/日志/导出) │
└──────────────────────────┬──────────────────────────────┘
                           │ HTTP (REST)
┌──────────────────────────▼──────────────────────────────┐
│                    Backend (FastAPI :8080)               │
│  ┌──────────┐  ┌──────────┐  ┌───────────────────────┐  │
│  │ routes/  │  │ models/  │  │ services/agent/       │  │
│  │ projects │  │ ORM+Schema│ │  ├─ core/  (loop,state)│  │
│  │ audits   │  │ (SQLAlch)│  │  ├─ tools/ (6+工具)   │  │
│  │ keys     │  │          │  │  ├─ skills/ (14包)    │  │
│  │ dashboard│  └────┬─────┘  │  ├─ scanners/ (SAST)  │  │
│  └──────────┘       │        │  ├─ rules/ (YAML)     │  │
│         │           │        │  ├─ verification/沙箱 │  │
│         │           │        │  ├─ export/ (SARIF)   │  │
│         │           │        │  ├─ prompts/          │  │
│  ┌──────▼───────────▼──────┐ │  ├─ orchestrator.py   │  │
│  │ SQLite (aiosqlite)      │ │  └─ service.py        │  │
│  │ code_audit.db           │ │  └── services/llm/    │  │
│  └─────────────────────────┘ │      11 厂商适配器    │  │
└──────────────────────────────┴───────────────────────┘
```

## 2. 模块职责

### 2.1 数据层（models/）

| 表 | 关键字段 | 说明 |
|----|---------|------|
| projects | id, name, path, tech_stack | 审计项目 |
| audits | id, project_id, **mode**(quick/smart/comprehensive), status, **stage**, **stages_completed**, **scan_candidates_count**, covered_files(JSON), llm_provider/model/api_key, max_turns, turns_completed, total_tokens, total_tool_calls, error_message | 审计记录 |
| findings | id, audit_id, vulnerability_type, severity, title, file_path, source, sink, exploit_chain, poc, suggestion, confidence, **cwe**, **poc_verified**, needs_verification | 漏洞发现 |
| audit_logs | id, audit_id, level, message | Agent 活动日志 |
| api_keys | id, provider, api_key(**加密**), last_status, last_error | LLM 密钥 |

### 2.2 阶段状态机（Audit.stage）

```
recon → scan → triage → finding → verification → finalize
```

按模式裁剪：

| 模式 | 阶段序列 |
|------|---------|
| quick | recon → scan → triage → finalize |
| smart | recon → finding → verification → finalize |
| comprehensive | recon → scan → triage → finding → verification → finalize |

- `stage`：当前阶段
- `stages_completed`：已完成阶段列表（JSON 数组）
- 状态流转在 `core/state.py::AgentState.mark_stage()` 中维护

### 2.3 Agent 核心（services/agent/）

#### core/loop.py — ReAct 循环
- `run()`：while status==running 循环，受 MAX_TURNS / MAX_TOOL_CALLS 硬上限约束
- `run_turn()`：记忆压缩 → 调 LLM（tools 注入）→ 执行工具调用 → 处理结果
- 5 类 NUDGE_MESSAGES：stuck_loop / payload_invalid / scan_required / low_coverage / no_progress
- `_is_stuck()`：连续同参工具调用达 MAX_STUCK_COUNT(3) 触发 stuck nudge
- `_coverage_check()`：finish_audit 前的覆盖度守卫（covered_files / 总文件数）
- `_scan_check()`：comprehensive 模式要求扫描完成才能 finish
- `_update_audit_status()`：把 state 持久化到 DB（status/stage/turns/tokens/covered）
- `auto_persist` + `_save_finding_safe()`：findings 批量落库（幂等，主键冲突静默跳过）

#### core/state.py — Agent 状态
- AgentState：messages / findings / covered_files / turn / tool_call_count / total_tokens / status / terminal_reason / **stage / stages_completed / scan_candidates**
- FindingRecord 数据类：完整漏洞记录（含 cwe / poc_verified）

#### core/memory.py — 上下文压缩（4 级管道）
1. Step1 截断工具结果（TOOL_RESULT_BUDGET=8000 字符）
2. Step2 滑窗（保留 system + 最近 12 条，旧消息启发式摘要）
3. Step3 微压缩（合并同工具连续结果、压缩空行）
4. Step4 LLM 摘要（loop 层调用 llm_summarize，找安全切点避免孤儿 tool 对）

- `_sanitize_tool_pairs()`：维护 assistant.tool_calls ↔ role=tool 配对不变量，防 400
- token 估算：4 字符/token；阈值 CONTEXT_WINDOW_TOKENS(128000) × COMPRESS_THRESHOLD(0.6)

#### core/registry.py — 工具注册
- ToolDefinition.to_openai_format()：生成 OpenAI function 格式
- ToolRegistry：register / get / describe / list_names

### 2.4 工具层（tools/agent_tools.py）

| 工具 | 说明 |
|------|------|
| read_file | 读文件，大小分流：>250 行只读头部 400 行（excerpt）；跳过生成文件（min.js/lock/vendor） |
| read_file_range | 指定行范围深读 |
| list_files | 列文件，限 200 条，跳过常规忽略目录 |
| grep | 优先 rg 输出 JSON，回退 Python 正则；单字段长度限制防 JSON 截断（**经 `asyncio.to_thread` 执行，不阻塞事件循环**） |
| get_project_structure | 项目结构树 |
| finalize_finding | 校验 7 必填字段 + 类型/严重级枚举 |
| finish_audit | 覆盖度守卫 + 扫描守卫 |
| run_engine_scan | 手动触发引擎扫描（Semgrep/SCA 经 `asyncio.to_thread`） |
| run_custom_rules | 执行自定义 YAML 规则 |
| verify_poc | PoC 静态校验（可选沙箱执行） |
| load_skill | 按需加载技能全文 |

安全：`_safe_path` 用 realpath + 前缀边界判断（`C:\proj` 不再匹配 `C:\projects\evil`）。

### 2.4b 代码导入层（services/ingest.py）

| 函数 | 说明 |
|------|------|
| ingest_zip(raw_bytes, filename) | 解压 zip 到 `UPLOADS_DIR`，含 zip-slip 路径穿越防护（`..`/绝对路径拒绝）、单层根目录自动扁平化、200MB 上限、技术栈自动探测 |
| ingest_git(url, branch?) | `git clone --depth 1` 浅克隆到 `UPLOADS_DIR`（URL 校验 + 超时保护） |

> 导入层让审计目标代码进入容器内目录，**彻底解耦宿主机路径**——这是 macOS / 任意平台可用的关键（容器不再需要访问宿主 `C:\` / `/Users`）。

### 2.5 引擎层（scanners/engine.py）

```
scan_project(project_path) → ScanResult(candidates, scans, engine_status)
```

- `run_semgrep()`：Semgrep OWASP 规则集，结果转 candidates
- `run_sca()`：pip-audit（requirements.txt）+ npm audit（package-lock.json），依赖漏洞转候选
- `run_custom_rules()`：rules/ YAML 规则
- **优雅降级**：CLI 不存在 → 记录 skipped，不崩溃

候选注入：扫描结果在审计启动时同步执行（asyncio.to_thread 避免阻塞事件循环），
注入 state.scan_candidates 并写入 system prompt 的 "Engine Scan Candidates" 区，LLM 逐条 Triage。

### 2.6 规则层（rules/loader.py）

- YAML 规则加载：id/type/severity/languages/patterns/message/cwe/exclude
- 内置 + 自定义（rules/custom_rules.yml）合并
- 供引擎与 LLM 工具共用

### 2.7 验证沙箱（verification/sandbox.py）

- 静态校验（始终开启）：AST 解析 + import 白名单 + 危险调用（os.system/subprocess/eval 等）拦截
- 可选沙箱执行（SANDBOX_ENABLED）：临时目录 + 超时 + 禁网络/禁危险库
- 输入：poc 代码 + 语言；输出：验证结果 + 详情

### 2.8 导出层（export/sarif.py）

- SARIF 2.1.0 builder：ruleId / level / location / properties
- CWE 映射表（16 类漏洞 → CWE 主编号）
- CVSS 3.1 评分（severity → base score）

### 2.9 编排层（orchestrator.py）

```
run(all_files) → {parallel: bool, chunks: [...], merged: [...], sub_states: [...]}
```

- 按顶层目录分块，每 Agent ≥ MIN_FILES_PER_AGENT(15) 文件
- 子 Agent 并行审计（asyncio.gather），独立 AgentState
- findings 合并去重（按 type+file_path+title 三元组）
- 大项目（>30 文件，分块 >1）自动触发；否则回退单循环

### 2.10 服务编排（service.py）

```
start_audit() →
  1. 建 Audit 记录（status=running, stage=recon）
  2. asyncio.create_task 后台执行 _run_audit_task
  3. _run_audit_task:
     a. 探测技术栈（标志文件 + package.json 依赖）
     b. 引擎预扫描（线程池）
     c. 发现文件清单（跳过忽略目录）
     d. 注册全部工具
     e. 组装 AgentState + ReActLoop
     f. 大项目 → Orchestrator.run()（并行）→ _save_finding_safe + _update_audit_status
       小项目 → loop.run()
  4. 异常 → status=failed + error_message
```

### 2.11 LLM 层（services/llm/）

- base_adapter.py：LLMAdapter 抽象（chat/summarize）+ ToolCall/TokenUsage/LLMResponse 数据类
- adapters/：11 家厂商（OpenAI 兼容类共用 openai_adapter）
- factory：按 provider 名创建

### 2.12 API 层（api/routes/）

| 路由 | 方法 | 说明 |
|------|------|------|
| /api/projects | POST/GET | 创建/列出项目 |
| /api/projects/{id} | GET/DELETE | 详情/删除 |
| /api/projects/{id}/audits | GET | 项目下审计列表 |
| /api/projects/upload | POST | 上传 zip 解压导入（返回 project） |
| /api/projects/clone | POST | Git 仓库浅克隆导入（返回 project） |
| /api/audits | POST/GET | 创建审计/列表 |
| /api/audits/batch | POST | 批量审计 |
| /api/audits/{id} | GET | 审计详情（含 stage/stages_completed/scan_candidates_count） |
| /api/audits/{id}/abort | POST | 中止 |
| /api/audits/{id}/resume | POST | 恢复 |
| /api/audits/{id}/findings | GET | findings 列表 |
| /api/audits/{id}/logs | GET | Agent 日志 |
| /api/audits/{id}/report | GET | Markdown 报告（CWE/CVSS/stage/coverage） |
| /api/audits/{id}/sarif | GET | SARIF 2.1.0 导出 |
| /api/audits/{id}/compare/{other} | GET | 审计对比 |
| /api/audits/stats | GET | Dashboard 统计 |
| /api/keys | GET/POST/PATCH/DELETE | API Key 管理（加密存储+掩码返回） |
| /api/keys/{id}/test, /api/keys/test | POST | 连通性测试 |
| /api/llm/providers | GET | 可用厂商列表 |

## 3. 关键数据流

### 3.1 审计启动

```
POST /api/audits {project_id, mode, llm_provider, ...}
  → create Audit(running, recon)
  → create_task(_run_audit_task)
      → detect_tech_stack(project_path)
      → engine.scan_project() → candidates
      → collect_files() → all_files
      → register_tools(registry)
      → build AgentState(stage=recon, scan_candidates=candidates)
      → len(all_files) > 30 && chunks > 1 ?
          → Orchestrator.run() 并行
          → merged findings → state.add_finding → _save_finding_safe → _update_audit_status
      : else
          → ReActLoop.run()（内部逐阶段推进 + 最终 _update_audit_status）
```

### 3.2 Agent 循环内

```
run_turn():
  memory.compress()          # 4 级压缩
  llm.chat(messages, tools)  # 注入工具描述
  if tool_calls:
      for each: registry.execute(name, args) → result
      state.messages.append(tool result)
  else:
      关键词完成判定 → finish_audit
      否则 → nudge
  state.turn++
```

### 3.3 findings 落库

```
finalize_finding 被 LLM 调用 → 格式校验（7 必填+枚举）→ 通过则
  → state.add_finding(FindingRecord)
  → auto_persist 开启时立即 _save_finding_safe（幂等）
  → 被拒则注入 payload_invalid nudge
```

## 4. 配置项（backend/app/core/config.py）

| 配置 | 默认 | 说明 |
|------|------|------|
| MAX_TURNS | 50 | 最大循环轮数（service 按文件数动态放大） |
| MAX_TOOL_CALLS | 200 | 最大工具调用数 |
| CONTEXT_WINDOW_TOKENS | 128000 | 上下文窗口估算 |
| COMPRESS_THRESHOLD | 0.6 | 压缩触发阈值 |
| TOOL_RESULT_BUDGET | 8000 | 单工具结果预算字符 |
| SANDBOX_ENABLED | False | PoC 沙箱执行开关 |
| MIN_FILES_PER_AGENT | 15 | 多 Agent 每代理最少文件数 |
| DATABASE_URL | sqlite+aiosqlite:///./code_audit.db | 数据库（Docker 下被 docker-compose 覆盖为 `sqlite+aiosqlite:////data/code_audit.db`，落在命名卷 `codeaudit-data`） |
| UPLOADS_DIR | ./uploads | 上传/克隆代码目录（Docker 下为 `/data/uploads`，落在 `codeaudit-data` 卷） |
| GIT_CLONE_TIMEOUT | 300 | git clone 超时（秒） |
| MAX_UPLOAD_MB | 200 | 上传 zip 大小上限 |

## 5. 已修复的关键 Bug 记录

1. **skills/manager.py matches() 死代码**：原 `return True` 导致 14 个技能无条件全注入 → 改按技术栈匹配
2. **grep JSON 截断**：原在 JSON 序列化后截断字符串 → 无效 JSON（JSONDecodeError）→ 改为限制单字段长度
3. **技能目录解析少一层**：解析到 backend/skills 而非项目根 skills → 修复后 14 包全部加载
4. **并行编排状态不持久化**：orchestrator 分支 findings 入库后未调 `_update_audit_status()`，审计记录卡在 running/recon/0 turns → 已补调用
5. **comprehensive 模式 finish 被 scan_required 永久拦截**：扫描完成后未置 `state.scanned=True` → 已修复
6. **resume 未传 mode**：`_run_audit_task` 兼容性 → 已修复
7. **_safe_path 前缀边界**：`C:\proj` 匹配 `C:\projects\evil` → realpath + 边界判断
8. **API Key 明文存储**：SQLite 明文 + API 明文回显 → Fernet 加密 + 掩码返回
9. **loop 死代码**：`_collect_scan_candidates` 含嵌套事件循环调用 → 已删除
10. **service.py 死代码**：`audit.completed_at = audit.completed_at` → 保留（无副作用，已注释说明）

### 5.1 安全与跨平台加固（本轮）

11. **`cryptography` 依赖缺失 → API Key 明文落库**：补依赖；加密失败改为显式报错并记日志，不再静默存明文
12. **加密主密钥写在镜像内**：容器重建后旧密文无法解密（全部 401）→ 主密钥文件改存数据卷 `/data/.enc_key` + 权限 600
13. **技能包删除路径穿越**：`delete_skill` 未校验名称，`../../data` 可删任意目录 → 名称正则 + realpath 边界校验
14. **技能包 zip 上传任意写文件**：写入前 realpath 边界校验，拒绝越界
15. **审计时同步阻塞事件循环**：grep / Semgrep / PoC 在事件循环内同步执行导致 API 卡死 → 全部改 `asyncio.to_thread`
16. **`create_task` 无引用被 GC + key 缺失留僵尸审计**：任务持强引用；先解析 key 再启动，缺失即落 `failed`
17. **并行分支存入未验证 findings**：改为入库 `verified` 结果，未对抗验证的不进报告
18. **resume 不解析 DB 内 key**：恢复审计必然失败 → resume 走统一 key 解析与解密
19. **PoC 沙箱逃逸**：黑名单补 `__import__` / `getattr` / dunder 属性；static 模式明确返回未验证（不再谎称已验证）
20. **SQLite `database is locked`**：WAL 模式 + `busy_timeout=30s`，避免并行子代理写库导致 finding 静默丢失
21. **Mac 无法新建项目**：原仅支持「本地路径」，容器内访问不到宿主机路径 → 新增上传压缩包 / Git 在线仓库两种来源（解耦宿主机路径）

## 6. 已知限制

- SQLite 本地库：不适合多实例并发部署；升级代码新增字段需手动 ALTER TABLE 迁移
- 引擎为模式匹配（Semgrep 规则），跨文件数据流分析能力有限（深挖依赖 LLM）
- 沙箱验证默认关闭；开启需自行保证运行环境隔离
- 前端仅展示，审计核心全在后端；前端刷新丢失实时进度（轮询恢复）
