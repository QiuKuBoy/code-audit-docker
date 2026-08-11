import { createContext, useContext, useState, useCallback, type ReactNode } from 'react'

export type Lang = 'zh' | 'en'

type Dict = Record<string, string>

const zh: Dict = {
  // App sidebar
  'app.name': 'Code Audit',
  'app.subtitle': 'AI 代码安全审计',
  'nav.dashboard': '仪表盘',
  'nav.projects': '项目',
  'nav.newProject': '新建项目',
  'nav.runtime': '本地运行时',

  // Projects page
  'projects.title': '项目',
  'projects.subtitle': '管理待审计的代码项目',
  'projects.new': '新建项目',
  'projects.empty': '暂无项目，创建一个开始审计',
  'projects.name': '项目名称',
  'projects.path': '项目路径（本地）',
  'projects.pathPlaceholder': 'E:\\my-project',
  'projects.desc': '描述（可选）',
  'projects.descPlaceholder': '简要描述',
  'projects.create': '创建',
  'projects.cancel': '取消',
  'projects.delete': '删除此项目？',

  'projects.all': '全部',
  'projects.completed': '已完成',
  'projects.inProgress': '进行中',
  'projects.archived': '已归档',
  'projects.unknown': '未知',
  'projects.status': '状态',
  'projects.noCompleted': '暂无已完成审计',
  'projects.noInProgress': '暂无进行中的审计',
  'projects.noArchived': '暂无已归档项目',


  'projects.language': '语言类型',
  'projects.languageAuto': '自动检测',
  'projects.languagePlaceholder': '选择项目语言类型',
  'projects.languageHint': '选择语言可跳过自动检测，确保 Agent 使用对应技能包',
  'nav.projectsExpand': '展开项目',
  'nav.projectsCollapse': '收起项目',
  'nav.noProjects': '暂无项目',
  'nav.projectStatus.completed': '已完成',
  'nav.projectStatus.inProgress': '进行中',
  'nav.projectStatus.unaudited': '未审计',
  'nav.hideCompleted': '新建时不显示已完成项目',


  'nav.skills': '技能包 Skill',
  'nav.mcp': 'MCP 服务',
  'skills.subtitle': '按漏洞产出效率排序的审计技能包，S 级为最高价值',
  'skills.search': '搜索技能...',
  'skills.sortedByEfficiency': '按产出效率排序',
  'skills.tierS': 'S 级 · 最高产出',
  'skills.tierA': 'A 级 · 高产出',
  'skills.tierB': 'B 级 · 中产出',
  'skills.tierC': 'C 级 · 辅助',
  'skills.view': '查看',
  'skills.enabled': '启用',
  'skills.disabled': '禁用',
  'mcp.subtitle': '外部知识连接器，为审计 Agent 提供 CVE / 漏洞模式查询',
  'mcp.configured': '已配置服务器',
  'mcp.enabled': '已启用',
  'mcp.tools': '工具',
  'mcp.calls': '调用次数',
  'mcp.empty': '暂无 MCP 服务器配置',
  'mcp.connected': '已连接',
  'mcp.failed': '连接失败',
  'mcp.testing': '测试中...',
  'mcp.test': '测试连接',
  'mcp.authEnabled': '已配置鉴权',
  'mcp.noAuth': '无鉴权',
  'mcp.toolList': '工具列表',
  'mcp.error': '错误',


  'skills.new': '新建技能',
  'skills.newTitle': '新建自定义技能包',
  'skills.name': '技能名称',
  'skills.namePlaceholder': '例如: jwt_audit',
  'skills.content': '技能内容 (Markdown)',
  'skills.contentPlaceholder': '# 技能标题\n\n## 审计方法\n...',
  'skills.create': '创建',
  'skills.deleteConfirm': '确定删除技能 {name} 吗？',
  'skills.builtinProtected': '内置技能不可删除',
  'skills.createSuccess': '技能已创建',
  'skills.deleteSuccess': '技能已删除',
  'skills.upload': '本地上传',
  'skills.uploadSuccess': '技能文件已上传并创建',
  'skills.uploadFailed': '上传失败',
  'mcp.add': '添加服务器',
  'mcp.addTitle': '添加 MCP 服务器',
  'mcp.name': '服务器名称',
  'mcp.namePlaceholder': '例如: src-wiki',
  'mcp.url': '服务器 URL',
  'mcp.urlPlaceholder': 'https://example.com/mcp',
  'mcp.headers': 'Headers (JSON)',
  'mcp.headersPlaceholder': '{"Authorization": "Bearer xxx"}',
  'mcp.descriptionPlaceholder': '服务器描述（可选）',
  'mcp.addBtn': '添加',
  'mcp.deleteConfirm': '确定删除 MCP 服务器 {name} 吗？',
  'mcp.configProtected': 'config.py 内置服务器不可删除（仅运行时添加的可删）',
  'mcp.addSuccess': '服务器已添加',
  'mcp.deleteSuccess': '服务器已删除',

  'projects.loading': '加载中...',

  // Project detail
  'detail.back': '返回',
  'detail.startAudit': '启动新审计',
  'detail.auditMode': '审计模式',
  'detail.llmProvider': 'LLM 提供商',
  'detail.model': '模型',
  'detail.apiKey': 'API Key',
  'detail.apiKeyRequired': '（必填，.env 未配置）',
  'detail.apiKeyPlaceholder': 'sk-...',
  'detail.apiKeyConfigured': '.env 已配置 API Key',
  'detail.advanced': '高级选项',
  'detail.maxTurns': '最大轮次',
  'detail.start': '启动审计',
  'detail.starting': '启动中...',
  'detail.auditHistory': '审计历史',
  'detail.noAudits': '暂无审计记录',
  'detail.quickScan': '快速扫描',
  'detail.smartAudit': '智能审计',
  'detail.comprehensive': '综合审计',
  'detail.mode.quick': '快速扫描',
  'detail.mode.smart': '智能审计',
  'detail.mode.comprehensive': '综合审计',
  'detail.configured': '已配置',
  'detail.notConfigured': '未配置',
  'detail.enterKeyPrompt': '请在下方填入 API Key，或先在 backend/.env 中配置',
  'detail.noKeyGoSettings': '请先在 Settings 中配置该 Provider 的 API Key',
  'detail.goSettings': '前往 Settings',
  'detail.noKeyForProvider': '该 Provider ({provider}) 尚未配置 API Key，请前往 Settings 添加',

  // Audit detail
  'audit.back': '返回',
  'audit.turns': '轮次',
  'audit.toolCalls': '工具调用',
  'audit.tokens': 'tokens',
  'audit.findings': '漏洞发现',
  'audit.logs': '日志',
  'audit.auditing': '审计中... 暂无发现',
  'audit.noFindings': '未发现漏洞',
  'audit.noLogs': '暂无日志',
  'audit.description': '描述',
  'audit.source': 'Source（入口点）',
  'audit.sink': 'Sink（执行点）',
  'audit.exploitChain': '攻击链',
  'audit.codeSnippet': '代码片段',
  'audit.poc': 'PoC 验证',
  'audit.fix': '修复建议',

  'audit.delete': '删除',
  'audit.deleteConfirm': '确定删除该审计及其全部发现和日志吗？此操作不可恢复。',
  'audit.deleteRunning': '审计进行中，请先中止再删除',
  'audit.deleted': '已删除审计 {n} 条（含发现 {f} 条，日志 {l} 条）',
  'audit.status.running': '运行中',
  'audit.status.completed': '已完成',
  'audit.status.failed': '失败',
  'audit.status.aborted': '已中止',
  'audit.status.pending': '等待中',
  'audit.status.max_turns': '达轮次上限',
  'audit.mode.quick': '快速扫描',
  'audit.mode.smart': '智能审计',
  'audit.mode.comprehensive': '综合审计',


  // Common
  'common.loading': '加载中...',
  'common.notFound': '未找到',

  // Dashboard
  'dashboard.title': '仪表盘',
  'dashboard.subtitle': '审计概览与统计',
  'dashboard.totalProjects': '总项目数',
  'dashboard.totalAudits': '总审计数',
  'dashboard.totalFindings': '总漏洞数',
  'dashboard.totalTokens': 'Token 消耗',
  'dashboard.totalToolCalls': '工具调用数',
  'dashboard.severityDist': '漏洞严重度分布',
  'dashboard.typeDist': '漏洞类型分布',
  'dashboard.statusDist': '审计状态分布',
  'dashboard.recentAudits': '最近审计',
  'dashboard.timeline': '漏洞趋势',
  'dashboard.critical': '严重',
  'dashboard.high': '高危',
  'dashboard.medium': '中危',
  'dashboard.low': '低危',
  'dashboard.noData': '暂无数据',

  // Audit actions
  'audit.abort': '中止',
  'audit.resume': '恢复',
  'audit.exportReport': '导出报告',
  'audit.aborting': '中止中...',
  'audit.resuming': '恢复中...',
  'audit.abortConfirm': '确定要中止此审计吗？',
  'audit.compare': '对比',
  'audit.compareTitle': '审计对比',
  'audit.onlyInA': '仅审计 A 有',
  'audit.onlyInB': '仅审计 B 有',
  'audit.common': '共有',
  'audit.selectCompare': '选择两个审计进行对比',

  // Batch
  'batch.title': '批量审计',
  'batch.selectProjects': '选择要审计的项目',
  'batch.start': '启动批量审计',
  'batch.starting': '启动中...',
  'batch.results': '批量审计结果',
  'batch.started': '已启动',
  'batch.failed': '失败',

  // Settings (API Keys)
  'settings.title': 'API Key 管理',
  'settings.subtitle': '管理各 LLM 提供商的 API Key，并测试连通性',
  'settings.new': '新增 API Key',
  'settings.empty': '暂无 API Key，新增一个开始使用',
  'settings.provider': '提供商',
  'settings.apiKey': 'API Key',
  'settings.baseUrl': '自定义 Base URL（可选）',
  'settings.model': '默认模型（可选）',
  'settings.label': '备注（可选）',
  'settings.save': '保存',
  'settings.cancel': '取消',
  'settings.test': '测试连通性',
  'settings.testing': '测试中...',
  'settings.delete': '删除',
  'settings.deleteConfirm': '确认删除此 API Key？此操作不可恢复。',
  'settings.lastTest': '最近测试',
  'settings.neverTested': '未测试',
  'settings.latency': '延迟',
  'settings.testOk': '✓ 连通正常',
  'settings.testFailed': '✗ 连通失败',
  'settings.providerLabel': '提供商名称',
  'settings.createKey': '创建 API Key',
  'settings.testingThenSave': '可先测试再保存',
}

const en: Dict = {
  'app.name': 'Code Audit',
  'app.subtitle': 'AI Security Audit',
  'nav.dashboard': 'Dashboard',
  'nav.projects': 'Projects',
  'nav.newProject': 'New Project',
  'nav.runtime': 'Local Runtime',






  'detail.back': 'Back',
  'detail.startAudit': 'Start New Audit',
  'detail.auditMode': 'Audit Mode',
  'detail.llmProvider': 'LLM Provider',
  'detail.model': 'Model',
  'detail.apiKey': 'API Key',
  'detail.apiKeyRequired': '(required, not in .env)',
  'detail.apiKeyPlaceholder': 'sk-...',
  'detail.apiKeyConfigured': 'API Key configured in .env',
  'detail.advanced': 'Advanced options',
  'detail.maxTurns': 'Max Turns',
  'detail.start': 'Start Audit',
  'detail.starting': 'Starting...',
  'detail.auditHistory': 'Audit History',
  'detail.noAudits': 'No audits yet.',
  'detail.quickScan': 'Quick Scan',
  'detail.smartAudit': 'Smart Audit',
  'detail.comprehensive': 'Comprehensive',
  'detail.mode.quick': 'Quick Scan',
  'detail.mode.smart': 'Smart Audit',
  'detail.mode.comprehensive': 'Comprehensive',
  'detail.configured': 'configured',
  'detail.notConfigured': 'not configured',
  'detail.enterKeyPrompt': 'Please enter your API Key below, or configure it in backend/.env first',
  'detail.noKeyGoSettings': 'Please configure the API Key for this provider in Settings first',
  'detail.goSettings': 'Go to Settings',
  'detail.noKeyForProvider': 'Provider ({provider}) has no API Key configured. Please add one in Settings',


  'common.loading': 'Loading...',
  'common.notFound': 'not found',

  // Dashboard
  'dashboard.title': 'Dashboard',
  'dashboard.subtitle': 'Audit overview & statistics',
  'dashboard.totalProjects': 'Total Projects',
  'dashboard.totalAudits': 'Total Audits',
  'dashboard.totalFindings': '漏洞总数',
  'dashboard.totalTokens': 'Token Usage',
  'dashboard.totalToolCalls': 'Tool Calls',
  'dashboard.severityDist': '漏洞严重级别分布',
  'dashboard.typeDist': '漏洞类型分布',
  'dashboard.statusDist': '审计状态分布',
  'dashboard.recentAudits': '最近审计',
  'dashboard.timeline': '漏洞趋势',
  'dashboard.critical': '严重',
  'dashboard.high': '高危',
  'dashboard.medium': '中危',
  'dashboard.low': '低危',
  'dashboard.noData': '暂无数据',

  // Audit actions

  // Batch

  // ── Enhanced Audit Detail ────────────────────────────────────
  'audit.pipeline': '审计流水线',
  'audit.orchestration': 'Agent 编排',
  'audit.overview': '总览',
  'audit.findingsTab': 'Findings',
  'audit.logsTab': 'Logs',
  'audit.report': 'Report',
  'audit.reportTitle': '代码安全审计报告',
  'audit.exportMd': 'Export Markdown',
  'audit.exportHtml': 'Export HTML',
  'audit.exportSarif': 'Export SARIF',
  'audit.printReport': 'Print Report',
  'audit.pageSize': '每页',
  'audit.showing': '显示',
  'audit.of': '共',
  'audit.items': '条',
  'audit.previous': '上一页',
  'audit.next': '下一页',
  'audit.noFindingsYet': '审计进行中，暂无发现...',
  'audit.coverage': '覆盖率',
  'audit.confirmed': 'Confirmed',
  'audit.rejected': 'False Positive',
  'audit.pending': 'Pending',
  'audit.mcpStatus': 'MCP Status',
  'audit.mcpConnected': '已连接',
  'audit.mcpDisconnected': '未连接',
  'audit.specialistActive': 'Active Specialists',
  'audit.reportLang': 'Report Language',
  'audit.reportZh': 'Chinese Report',
  'audit.reportEn': 'English Report',

  // ── Enhanced Dashboard ───────────────────────────────────────
  'dash.agentHealth': 'Agent Health',
  'dash.mcpServers': 'MCP Servers',
  'dash.activeSessions': 'Active Sessions',
  'dash.cacheHitRate': 'Cache Hit Rate',
  'dash.auditTrend': 'Audit Trend',
  'dash.coverageRate': 'Avg Coverage',
  'dash.topVulnerabilities': 'Top Vulnerabilities',
  'dash.topFiles': 'High-Risk Files',

  // ── Status Bar ───────────────────────────────────────────────
  'statusbar.connected': 'Connected',
  'statusbar.model': 'Model',
  'statusbar.uptime': 'Uptime',
  'statusbar.version': 'Version',

  'batch.title': 'Batch Audit',
  'batch.selectProjects': 'Select projects to audit',
  'batch.start': 'Start Batch Audit',
  'batch.starting': 'Starting...',
  'batch.results': 'Batch Results',
  'batch.started': 'Started',
  'batch.failed': 'Failed',

  // Settings (API Keys)
  'settings.title': 'API Key Management',
  'settings.subtitle': 'Manage LLM provider keys and test connectivity',
  'settings.new': 'Add API Key',
  'settings.empty': 'No API keys yet. Add one to start.',
  'settings.provider': 'Provider',
  'settings.apiKey': 'API Key',
  'settings.baseUrl': 'Custom Base URL (optional)',
  'settings.model': 'Default Model (optional)',
  'settings.label': 'Note (optional)',
  'settings.save': 'Save',
  'settings.cancel': 'Cancel',
  'settings.test': 'Test Connectivity',
  'settings.testing': 'Testing...',
  'settings.delete': 'Delete',
  'settings.deleteConfirm': 'Delete this API key? This cannot be undone.',
  'settings.lastTest': 'Last tested',
  'settings.neverTested': 'Never tested',
  'settings.latency': 'latency',
  'settings.testOk': '✓ Reachable',
  'settings.testFailed': '✗ Failed',
  'settings.providerLabel': 'Provider Name',
  'settings.createKey': 'Create API Key',
  'settings.testingThenSave': 'You can test before saving',

  'skills.upload': 'Upload',
  'skills.uploadSuccess': 'Skill uploaded and created',
  'skills.uploadFailed': 'Upload failed',
}

const dicts: Record<Lang, Dict> = { zh, en }

interface I18nCtx {
  lang: Lang
  t: (key: string) => string
  setLang: (lang: Lang) => void
  toggle: () => void
}

const Ctx = createContext<I18nCtx | null>(null)

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLang] = useState<Lang>(() => {
    // Persist in localStorage
    const saved = typeof localStorage !== 'undefined' ? localStorage.getItem('code-audit-lang') : null
    return (saved === 'en' || saved === 'zh') ? saved : 'zh'
  })

  const t = useCallback((key: string) => {
    return dicts[lang][key] ?? key
  }, [lang])

  const toggle = useCallback(() => {
    setLang(prev => {
      const next = prev === 'zh' ? 'en' : 'zh'
      localStorage.setItem('code-audit-lang', next)
      return next
    })
  }, [])

  return (
    <Ctx.Provider value={{ lang, t, setLang, toggle }}>
      {children}
    </Ctx.Provider>
  )
}

export function useI18n() {
  const ctx = useContext(Ctx)
  if (!ctx) throw new Error('useI18n must be used within I18nProvider')
  return ctx
}
