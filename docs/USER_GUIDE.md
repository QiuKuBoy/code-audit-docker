# 用户手册（User Guide）

本文档面向**使用者**：如何安装、配置、启动，以及完整使用 Code Audit 平台进行代码安全审计。

---

## 1. 环境要求

| 依赖 | 版本要求 | 说明 |
|------|---------|------|
| Docker | 24+（含 Compose v2） | **推荐部署方式**，Windows / macOS / Linux 行为一致 |
| Python | 3.11+ | 仅「本地开发模式」需要 |
| Node.js | 20+ | 仅「本地开发模式」需要（vite 构建前端） |
| （可选）Semgrep | 最新版 | SAST 引擎，`pip install semgrep` |
| （可选）pip-audit | 最新版 | Python 依赖扫描，`pip install pip-audit` |

> **跨平台说明（macOS / Linux / Windows 通用）**：后端运行在容器（或本机）内，审计目标代码通过「上传压缩包」或「在线 Git 仓库」进入后端目录。因此不再依赖宿主机本地路径，**Mac 用户也能正常使用**。早期版本只支持「本地路径」，容器访问不到 Mac 的 `/Users/...` 路径而失败，该问题已修复。

## 2. 安装与启动

### 2.1 Docker 一键部署（推荐，全平台通用）

```bash
cd code-audit-docker
cp .env.example .env          # 可选：填入 LLM API Key，留空也可稍后在网页添加
docker compose up -d --build  # 多阶段构建：Node 构建前端 → Python 运行后端
```

启动成功后：
- 前端界面：http://localhost:8080
- API 文档（Swagger）：http://localhost:8080/docs

数据持久化：数据库与上传代码落在命名卷 `codeaudit-data`（`/data`），技能包落在 `codeaudit-skills`，容器重建不丢。

常用命令：

```bash
docker compose logs -f          # 查看日志
docker compose restart          # 重启
docker compose down             # 停止（保留数据卷）
docker compose down -v          # 停止并删除数据卷（慎用）
```

### 2.2 本地开发模式（不依赖 Docker）

**后端**：

```bash
cd backend
python -m venv .venv
source .venv/bin/activate        # Windows: .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
```

**前端**（开发热更新或生产构建）：

```bash
cd frontend
npm install
npm run dev        # 开发服务器 http://localhost:5173（代理 /api → 8080）
# 或生产构建（产物 frontend/dist 由后端静态托管）
npm run build
```

> 本地开发模式的 `.env` 使用 `backend/.venv` 同级目录的 `backend/.env`（从 `backend/.env.example` 复制）；Docker 模式使用项目根目录 `.env`。两者字段一致。

## 3. 配置

### 3.1 LLM API Key（必需）

**网页方式（推荐）**：
1. 打开 http://localhost:8080
2. 进入「设置 / API Keys」页
3. 选择厂商（DeepSeek / OpenAI / Anthropic / Gemini / Doubao / MiniMax / Baidu / Zhipu / Qwen / Kimi / SiliconFlow）
4. 填入 API Key，保存

**文件方式**：
```bash
cd backend
copy .env.example .env
# 编辑 .env，填入 DEEPSEEK_API_KEY=sk-xxx 等
```

安全特性：
- Key 使用 **Fernet 加密存储**（主密钥：环境变量 `API_KEY_ENCRYPTION_KEY`，未设置时用机器级 `.enc_key` 文件）
- API 接口返回时**掩码显示**（如 `sk-*********************7890`），不泄露明文
- 旧版明文数据自动兼容解密迁移

### 3.2 可选引擎配置

```bash
# 强烈推荐安装（大幅提升模式化漏洞检出率）
pip install semgrep pip-audit
```

安装后重启服务即可生效。未安装时审计自动降级为「纯 LLM + 自定义规则」模式，不报错。

### 3.3 自定义规则（rule-as-code）

在 `rules/` 目录放置 YAML 规则文件即可自动加载。示例 `rules/custom_rules.yml`：

```yaml
- id: CUSTOM-EVAL
  type: dangerous-function
  severity: HIGH
  languages: [python, javascript]
  patterns:
    - eval(
    - exec(
  message: "Detected eval/exec usage"
  cwe: "CWE-95"
```

字段说明：
| 字段 | 必填 | 说明 |
|------|------|------|
| id | ✅ | 规则唯一 ID |
| type | ✅ | dangerous-function / dangerous-import / weak-crypto / hardcoded-secret 等 |
| severity | ✅ | CRITICAL / HIGH / MEDIUM / LOW |
| languages | ✅ | python / javascript / java / php 等 |
| patterns | ✅ | 字符串匹配模式列表（命中任一即告警） |
| message | 否 | 告警消息 |
| cwe | 否 | 映射的 CWE 编号 |
| exclude | 否 | 排除的文件 glob（如 `["**/test_*.py"]`） |

## 4. 完整使用流程

### 4.1 新建项目

点击「新建项目」，提供**三种代码来源**（任选其一）：

1. **上传压缩包（推荐，Mac / Docker / Windows 通用）**
   - 选择本地 `.zip` 文件上传，后端自动解压（含 zip-slip 防护、单层目录自动扁平化、200MB 上限）
   - 可勾选「创建后立即启动审计」，选好模式 + LLM 后直接开始
2. **在线仓库**
   - 填入 Git 仓库 URL（支持 `https://` 与 `git@` 形式），后端执行 `git clone --depth 1` 浅克隆
   - 同样支持创建后直接启动审计
3. **本地路径**
   - 仅当后端运行在本机（本地开发模式）时可用，直接输入本地代码目录绝对路径
   - Docker 部署时容器内不存在宿主机路径，请用前两种方式

保存后系统自动探测技术栈（识别 `package.json` / `requirements.txt` / `pom.xml` / `go.mod` 等）。

### 4.2 启动审计

进入项目详情，选择：

| 模式 | 适用场景 |
|------|---------|
| ⚡ Quick（快速扫描） | 快速覆盖，引擎扫描 + 误报过滤，适合 CI 快速检查 |
| 🧠 Smart（智能审计） | 深度人工挖掘，适合 0day / 高危漏洞研究 |
| 🔍 Comprehensive（综合审计） | 全量审计（引擎 + 深度 + 验证），最彻底但最耗时 |

然后选择：
- **LLM 厂商**：如 DeepSeek
- **模型**：如 deepseek-v4-flash

点击「开始审计」。

### 4.3 观察审计进度

审计详情页实时展示：
- **阶段进度条**：Recon → Scan → Triage → Finding → Verification → Finalize（不同模式阶段不同）
- **Agent 日志流**：工具调用、LLM 思考过程
- **Findings 实时入库**：已确认的漏洞即时显示

大项目（>30 个源文件）自动触发**多 Agent 并行编排**：按目录分块 → 并行子审计 → findings 去重合并。

### 4.4 审计控制

| 操作 | 说明 |
|------|------|
| 中止（Abort） | 仅 running/pending 状态可中止 |
| 恢复（Resume） | aborted/failed/paused 状态可重启继续 |

### 4.5 查看与导出结果

- **Findings 列表**：按严重级排序，含 CWE、CVSS、poc_verified 标记
- **Markdown 报告**：详情页「导出报告」按钮，含 Summary 表 + 每漏洞完整分析
- **SARIF 导出**：详情页「SARIF」按钮，或 `GET /api/audits/{audit_id}/sarif`，可直接导入 GitHub Code Scanning / GitLab SAST

### 4.6 批量审计

支持一次对多个项目批量发起审计（Batch），在项目列表页选择多个项目后操作。

### 4.7 审计对比

两个审计记录之间对比，按（漏洞类型, 文件路径, 标题）三元组匹配，输出：
- 仅 A 有 / 仅 B 有 / 共有 — 用于评估不同模式、不同 LLM 的效果差异

## 5. Dashboard 统计

首页 Dashboard 展示：
- 总项目数 / 总审计数 / 总 findings 数
- token 消耗与工具调用总量
- findings 按 severity / 类型分布
- 审计状态分布（completed / failed / max_turns / aborted）
- severity 时间线

## 6. 常见问题（FAQ）

### Q1: 审计一直停在 Recon 阶段？
- 确认 LLM API Key 有效（查看审计 error_message）
- 确认可选引擎是否卡住（Semgrep 首次运行需下载规则，可能较慢）
- 如果是并行编排模式且 finds 已入库但状态未更新：属已修复的旧 bug，升级代码后重跑即可

### Q2: 报错 `LLM error: 401 Authentication Fails`？
API Key 无效或额度不足。在设置页重新配置，或用「测试」按钮验证连通性。

### Q3: 审计很快结束且 findings 很少？
- 检查是否装了 Semgrep（引擎候选能显著提升检出率）
- 确认模式选择：Quick 偏快速扫描，Smart 才做深度挖掘
- 项目可能太小或覆盖度守卫被绕过

### Q4: 如何查看某次审计的完整日志？
审计详情页「日志」Tab，或 `GET /api/audits/{audit_id}/logs`。

### Q5: 数据库在哪里？如何备份？
- **Docker 部署**：数据库在命名卷 `codeaudit-data` 内的 `/data/code_audit.db`。备份方式：`docker compose down` 后复制卷数据，或直接 `docker run --rm -v codeaudit-data:/data -v $(pwd):/backup busybox cp /data/code_audit.db /backup/code_audit.db`。
- **本地开发模式**：`backend/code_audit.db`（SQLite）。直接复制文件即可备份。
- 建议升级/迁移前先备份。

### Q6: 如何重置数据？
- **Docker 部署**：`docker compose down -v` 删除数据卷（**会清空所有项目、审计、密钥**），再 `docker compose up -d` 重建空库。
- **本地开发模式**：停止服务后删除 `backend/code_audit.db`，重启服务自动重建空库。

> 清除所有 API Key：在网页「设置 / API Keys」页逐条删除，或执行 `DELETE FROM api_keys;`（数据库）。

### Q7: macOS 无法新建项目 / 报路径错误？
早期版本仅支持「本地路径」，而 Docker 容器内访问不到 Mac 的 `/Users/...` 路径。请改用「上传压缩包」或「在线仓库」两种来源（已内置修复）。

## 7. 安全注意事项

- 本工具用于**授权**的代码审计，请勿用于未授权目标
- API Key 加密存储，但数据库文件仍属敏感资产，注意访问控制
- 沙箱验证（PoC 执行）默认关闭（`SANDBOX_ENABLED=False`），开启时确保运行环境隔离
- 服务默认监听 `0.0.0.0`，如仅在本地使用建议加防火墙限制或改 `--host 127.0.0.1`
