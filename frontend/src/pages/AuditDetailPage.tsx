
import { useState, useEffect, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  ArrowLeft, Bug, FileCode, Terminal, Clock, ChevronDown, ChevronRight,
  StopCircle, PlayCircle, Download, ShieldCheck, Layers, GitBranch,
  Globe, FileText, Printer, ChevronLeft, Server, Cpu
} from 'lucide-react'
import { api } from '../services/api'
import type { Audit, Finding, AuditLog } from '../types'
import { useI18n } from '../i18n'

/* ── Constants ──────────────────────────────────────────────── */

const SEVERITY_COLORS: Record<string, string> = {
  CRITICAL: 'bg-severity-critical/10 text-severity-critical border-severity-critical/30',
  HIGH: 'bg-severity-high/10 text-severity-high border-severity-high/30',
  MEDIUM: 'bg-severity-medium/10 text-severity-medium border-severity-medium/30',
  LOW: 'bg-severity-low/10 text-severity-low border-severity-low/30',
}

const SEVERITY_DOT: Record<string, string> = {
  CRITICAL: '#ef4444', HIGH: '#f97316', MEDIUM: '#eab308', LOW: '#3b82f6',
}

const SEV_LABELS_ZH: Record<string, string> = {
  CRITICAL: '严重', HIGH: '高危', MEDIUM: '中危', LOW: '低危',
}

const STATUS_LABELS: Record<string, string> = {
  running: '运行中', completed: '已完成', failed: '失败',
  aborted: '已中止', pending: '等待中', max_turns: '达轮次上限',
}

const STAGE_ORDER = ['recon', 'scan', 'triage', 'finding', 'verification', 'finalize']
const STAGE_LABELS: Record<string, string> = {
  recon: '侦察', scan: '扫描', triage: '研判',
  finding: '深挖', verification: '验证', finalize: '定稿',
}
const STAGE_ICONS: Record<string, string> = {
  recon: '\ud83d\udd0d', scan: '\ud83d\udee1\ufe0f', triage: '\ud83d\udcca',
  finding: '\ud83d\udc1b', verification: '\u2705', finalize: '\ud83d\udccb',
}

/* ── Pipeline Visualizer ────────────────────────────────────── */

function PipelineVisualizer({ audit }: { audit: Audit }) {
  const done = new Set(audit.stages_completed || [])
  if (audit.stage) done.add(audit.stage)
  const currentIdx = audit.stage ? STAGE_ORDER.indexOf(audit.stage) : -1
  const isRunning = audit.status === 'running'

  return (
    <div className="pipeline-container">
      <div className="flex items-center gap-0 pipeline-track">
        {STAGE_ORDER.map((s, i) => {
          const isDone = done.has(s)
          const isCurrent = audit.stage === s
          const isPast = currentIdx >= 0 && i < currentIdx
          return (
            <div key={s} className="flex items-center flex-1">
              {/* Stage node */}
              <div className={`pipeline-node ${isDone ? 'done' : isCurrent ? 'current' : isPast ? 'past' : 'pending'}`}>
                <span className="text-sm">{STAGE_ICONS[s]}</span>
                <span className="text-[10px] font-bold mt-0.5">{STAGE_LABELS[s]}</span>
                {isCurrent && isRunning && <span className="pipeline-pulse" />}
                {isDone && <span className="pipeline-check">✓</span>}
              </div>
              {/* Connector */}
              {i < STAGE_ORDER.length - 1 && (
                <div className={`flex-1 h-0.5 mx-1 rounded-full ${isDone ? 'bg-green-500/60' : isPast ? 'bg-green-500/30' : 'bg-border'}`}>
                  {isPast && <div className="h-full bg-green-500/60 rounded-full animate-[pipelineFill_0.5s_ease-out]" style={{ width: '100%' }} />}
                </div>
              )}
            </div>
          )
        })}
      </div>
      {audit.scan_candidates_count > 0 && (
        <div className="text-[10px] text-text-muted mt-2 ml-1">
          Engine candidates: {audit.scan_candidates_count}
        </div>
      )}
    </div>
  )
}

/* ── Agent Orchestration Diagram ─────────────────────────────── */

function AgentOrchestration({ audit }: { audit: Audit }) {
  const isRunning = audit.status === 'running'
  const isOrch = audit.turns_completed === 0 && audit.total_tool_calls === 0

  const agents = [
    { id: 'recon', label: 'Recon', icon: '\ud83d\udd0d', color: '#6366f1', desc: 'Project structure, entry points, tech stack' },
    { id: 'saast', label: 'SAST', icon: '\ud83d\udee1\ufe0f', color: '#8b5cf6', desc: 'Semgrep + Custom Rules' },
  ]

  if (isOrch) {
    agents.push(
      { id: 'orch', label: 'Orch', icon: '\ud83d\udd17', color: '#f59e0b', desc: 'Multi-agent parallel orchestration' },
      { id: 'sub1', label: 'Agent 1', icon: '\ud83e\udd16', color: '#10b981', desc: 'Module chunk audit' },
      { id: 'sub2', label: 'Agent 2', icon: '\ud83e\udd16', color: '#10b981', desc: 'Module chunk audit' },
    )
  }

  agents.push(
    { id: 'verify', label: 'Verify', icon: '\u2705', color: '#06b6d4', desc: 'PoC validation + adversarial review' },
    { id: 'report', label: 'Report', icon: '\ud83d\udccb', color: '#ec4899', desc: 'SARIF / MD / HTML export' },
  )

  return (
    <div className="orch-container">
      <div className="flex items-center gap-2 mb-3">
        <GitBranch className="w-4 h-4 text-accent" />
        <span className="text-xs font-semibold text-text-muted uppercase tracking-wider">Agent Orchestration</span>
        {isRunning && <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />}
      </div>
      <div className="flex items-center gap-2 flex-wrap">
        {agents.map((a, i) => (
          <div key={a.id} className="flex items-center gap-0">
            <div className="orch-node" style={{ borderColor: a.color + '40' }}>
              <span className="text-base">{a.icon}</span>
              <span className="text-[10px] font-bold mt-0.5" style={{ color: a.color }}>{a.label}</span>
            </div>
            {i < agents.length - 1 && (
              <span className="orch-arrow" style={{ color: a.color + '80' }}>→</span>
            )}
          </div>
        ))}
      </div>
      <div className="flex gap-3 mt-2 flex-wrap">
        {agents.map(a => (
          <div key={a.id} className="text-[10px] text-text-dim max-w-[120px]">{a.desc}</div>
        ))}
      </div>
    </div>
  )
}

/* ── Paginated Findings Table ────────────────────────────────── */

function FindingsTable({ findings, isRunning }: { findings: Finding[]; isRunning: boolean }) {
  const { t } = useI18n()
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [reportLang, setReportLang] = useState<'zh' | 'en'>('zh')

  const total = findings.length
  const totalPages = Math.max(1, Math.ceil(total / pageSize))
  const start = (page - 1) * pageSize
  const paged = findings.slice(start, start + pageSize)

  if (total === 0) {
    return (
      <div className="text-center py-16 text-text-muted">
        <Bug className="w-10 h-10 mx-auto mb-3 opacity-40" />
        <p className="text-sm">{isRunning ? t('audit.noFindingsYet') : t('audit.noFindings')}</p>
      </div>
    )
  }

  const severityOrder = { CRITICAL: 0, HIGH: 1, MEDIUM: 2, LOW: 3 }

  const getVulnNameZh = (type: string) => {
    const map: Record<string, string> = {
      SQL_Injection: 'SQL 注入', XSS: '跨站脚本', SSRF: '服务端请求伪造',
      Path_Traversal: '路径遍历', Deserialization: '反序列化', Authentication_Bypass: '认证绕过',
      Authorization_Failure: '授权失败', RCE: '远程代码执行', XXE: 'XML 外部实体',
      Open_Redirect: '开放重定向', Race_Condition: '竞态条件', Business_Logic: '业务逻辑',
      Info_Disclosure: '信息泄露', Hardcoded_Secret: '硬编码密钥', Crypto_Issue: '加密问题',
      Known_Vulnerable_Dependency: '已知漏洞依赖',
    }
    return map[type] || type
  }

  return (
    <div>
      {/* Toolbar */}
      <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
        {/* Report language toggle */}
        <div className="flex items-center gap-1 bg-bg rounded-lg p-0.5 border border-border">
          <button onClick={() => setReportLang('zh')}
            className={`px-2.5 py-1 text-xs rounded-md transition-colors ${reportLang === 'zh' ? 'bg-accent/20 text-accent' : 'text-text-muted hover:text-text'}`}>
            <Globe className="w-3 h-3 inline mr-1" />{t('audit.reportZh')}
          </button>
          <button onClick={() => setReportLang('en')}
            className={`px-2.5 py-1 text-xs rounded-md transition-colors ${reportLang === 'en' ? 'bg-accent/20 text-accent' : 'text-text-muted hover:text-text'}`}>
            <Globe className="w-3 h-3 inline mr-1" />{t('audit.reportEn')}
          </button>
        </div>
        {/* Page size */}
        <div className="flex items-center gap-2 text-xs text-text-muted">
          <span>{t('audit.pageSize')}</span>
          {[10, 20, 100].map(n => (
            <button key={n} onClick={() => { setPageSize(n); setPage(1) }}
              className={`px-2 py-0.5 rounded border transition-colors ${pageSize === n ? 'border-accent/40 bg-accent/10 text-accent' : 'border-border hover:border-text-dim'}`}>
              {n}
            </button>
          ))}
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border text-text-dim text-[11px] uppercase tracking-wider">
              <th className="text-left p-3 w-16">#</th>
              <th className="text-left p-3">严重级别</th>
              <th className="text-left p-3">类型</th>
              <th className="text-left p-3">标题</th>
              <th className="text-left p-3 hidden md:table-cell">File</th>
              <th className="text-left p-3 w-16">CWE</th>
              <th className="text-left p-3 w-16">置信</th>
            </tr>
          </thead>
          <tbody>
            {paged.map((f, i) => (
              <>
                <tr key={f.id}
                  onClick={() => setExpandedId(expandedId === f.id ? null : f.id)}
                  className="border-b border-border/50 hover:bg-bg-hover/30 cursor-pointer transition-colors group">
                  <td className="p-3 text-text-dim font-mono text-xs">{start + i + 1}</td>
                  <td className="p-3">
                    <span className="flex items-center gap-1.5">
                      <span className="w-2 h-2 rounded-full" style={{ background: SEVERITY_DOT[f.severity] }} />
                      <span className={`px-1.5 py-0.5 text-[10px] font-bold rounded border ${SEVERITY_COLORS[f.severity]}`}>
                        {f.severity}
                      </span>
                    </span>
                  </td>
                  <td className="p-3">
                    <span className="text-xs">
                      {reportLang === 'zh' ? getVulnNameZh(f.vulnerability_type) : f.vulnerability_type.replace(/_/g, ' ')}
                    </span>
                  </td>
                  <td className="p-3 font-medium max-w-[300px] truncate">{f.title}</td>
                  <td className="p-3 text-text-muted font-mono text-[11px] hidden md:table-cell max-w-[250px] truncate">
                    {f.file_path}{f.line_start > 0 ? `:${f.line_start}` : ''}
                  </td>
                  <td className="p-3">
                    {f.cwe ? <span className="text-[10px] px-1.5 py-0.5 rounded bg-bg-hover font-mono">{f.cwe}</span> : '—'}
                  </td>
                  <td className="p-3">
                    <span className={`text-[10px] px-1.5 py-0.5 rounded ${f.confidence === 'HIGH' ? 'bg-green-500/10 text-green-500' : 'bg-severity-medium/10 text-severity-medium'}`}>
                      {f.confidence}
                    </span>
                  </td>
                </tr>
                {/* Expanded details */}
                {expandedId === f.id && (
                  <tr key={`${f.id}-exp`}>
                    <td colSpan={7} className="p-4 bg-bg-hover/20 border-b border-border/50">
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                        {f.description && (
                          <div className="md:col-span-2">
                            <h5 className="text-[10px] font-bold text-text-dim uppercase mb-1">Description</h5>
                            <p className="text-text-muted">{f.description}</p>
                          </div>
                        )}
                        <div>
                          <h5 className="text-[10px] font-bold text-text-dim uppercase mb-1">Source (Entry)</h5>
                          <code className="text-xs text-severity-medium bg-bg px-2 py-1 rounded block">{f.source}</code>
                        </div>
                        <div>
                          <h5 className="text-[10px] font-bold text-text-dim uppercase mb-1">Sink (Execution)</h5>
                          <code className="text-xs text-severity-high bg-bg px-2 py-1 rounded block">{f.sink}</code>
                        </div>
                        <div className="md:col-span-2">
                          <h5 className="text-[10px] font-bold text-text-dim uppercase mb-1">Exploit Chain</h5>
                          <pre className="text-xs text-text-muted bg-bg p-3 rounded-lg overflow-x-auto whitespace-pre-wrap">{f.exploit_chain}</pre>
                        </div>
                        {f.code_snippet && (
                          <div className="md:col-span-2">
                            <h5 className="text-[10px] font-bold text-text-dim uppercase mb-1">Code Snippet</h5>
                            <pre className="text-xs bg-bg p-3 rounded-lg overflow-x-auto border-l-2 border-severity-high/50">{f.code_snippet}</pre>
                          </div>
                        )}
                        {f.suggestion && (
                          <div className="md:col-span-2">
                            <h5 className="text-[10px] font-bold text-text-dim uppercase mb-1">Suggested Fix</h5>
                            <p className="text-green-500 text-xs">{f.suggestion}</p>
                          </div>
                        )}
                      </div>
                    </td>
                  </tr>
                )}
              </>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between mt-4 text-xs text-text-muted flex-wrap gap-2">
          <span>{t('audit.showing')} {start + 1}–{Math.min(start + pageSize, total)} {t('audit.of')} {total} {t('audit.items')}</span>
          <div className="flex items-center gap-1">
            <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}
              className="px-2 py-1 rounded border border-border hover:bg-bg-hover disabled:opacity-30 transition-colors">
              <ChevronLeft className="w-3.5 h-3.5" />
            </button>
            {Array.from({ length: Math.min(7, totalPages) }, (_, i) => {
              let num: number
              if (totalPages <= 7) num = i + 1
              else if (page <= 4) num = i + 1
              else if (page >= totalPages - 3) num = totalPages - 6 + i
              else num = page - 3 + i
              return (
                <button key={num} onClick={() => setPage(num)}
                  className={`w-7 h-7 rounded text-xs font-medium transition-colors ${page === num ? 'bg-accent text-white' : 'hover:bg-bg-hover text-text-muted'}`}>
                  {num}
                </button>
              )
            })}
            <button onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page === totalPages}
              className="px-2 py-1 rounded border border-border hover:bg-bg-hover disabled:opacity-30 transition-colors">
              <ChevronRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

/* ── Status Bar (sticky bottom) ──────────────────────────────── */

function StatusBar({ audit }: { audit: Audit }) {
  const { t } = useI18n()
  const isRunning = audit.status === 'running'
  const coverage = audit.covered_files?.length || 0

  return (
    <div className="status-bar">
      <div className="flex items-center gap-6 flex-wrap">
        <StatusItem icon={<Server className="w-3 h-3" />} label={t('audit.mcpStatus')}>
          <span className="flex items-center gap-1">
            <span className="w-1.5 h-1.5 bg-green-500 rounded-full" />
            <span className="text-green-500 text-xs">{t('audit.mcpConnected')}</span>
          </span>
        </StatusItem>
        <StatusItem icon={<Cpu className="w-3 h-3" />} label={t('statusbar.model')}>
          <span className="text-xs">{audit.llm_provider}</span>
        </StatusItem>
        <StatusItem icon={<Layers className="w-3 h-3" />} label={t('audit.coverage')}>
          <span className="text-xs font-mono">{coverage} files</span>
        </StatusItem>
        <StatusItem icon={<Globe className="w-3 h-3" />} label={t('statusbar.version')}>
          <span className="text-xs font-mono">v1.1.0</span>
        </StatusItem>
      </div>
      <div className="flex items-center gap-4">
        <StatusItem icon={<Clock className="w-3 h-3" />} label={t('statusbar.uptime')}>
          <span className="text-xs">{isRunning ? '● Running' : '● ' + audit.status}</span>
        </StatusItem>
        <span className="text-[10px] text-text-dim">
          {audit.turns_completed} turns · {audit.total_tool_calls} calls · {(audit.total_tokens / 1000).toFixed(1)}K tokens
        </span>
      </div>
    </div>
  )
}

function StatusItem({ icon, label, children }: { icon: React.ReactNode; label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center gap-1.5">
      <span className="text-text-dim">{icon}</span>
      <span className="text-[10px] text-text-dim uppercase">{label}:</span>
      {children}
    </div>
  )
}

/* ── Main Page ───────────────────────────────────────────────── */

export default function AuditDetailPage() {
  const { t } = useI18n()
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [audit, setAudit] = useState<Audit | null>(null)
  const [findings, setFindings] = useState<Finding[]>([])
  const [logs, setLogs] = useState<AuditLog[]>([])
  const [tab, setTab] = useState<'overview' | 'findings' | 'logs' | 'report'>('overview')
  const [actionLoading, setActionLoading] = useState(false)

  const load = useCallback(async () => {
    if (!id) return
    try {
      const [a, f, l] = await Promise.all([
        api.getAudit(id), api.getAuditFindings(id), api.getAuditLogs(id, 200),
      ])
      setAudit(a); setFindings(f); setLogs(l)
    } catch (_) {}
  }, [id])

  useEffect(() => {
    load()
    const ival = setInterval(() => { if (audit?.status === 'running') load() }, 3000)
    return () => clearInterval(ival)
  }, [id, audit?.status])

  if (!audit) return <div className="p-8 text-text-muted">{t('common.loading')}</div>

  const isRunning = audit.status === 'running'

  const handleAbort = async () => {
    if (!id || !confirm(t('audit.abortConfirm'))) return
    setActionLoading(true)
    try { await api.abortAudit(id); await load() } catch (e: any) { alert(e.message) } finally { setActionLoading(false) }
  }

  const handleResume = async () => {
    if (!id) return
    setActionLoading(true)
    try { await api.resumeAudit(id); await load() } catch (e: any) { alert(e.message) } finally { setActionLoading(false) }
  }

  const handleExportMd = async () => {
    if (!id) return
    try {
      const md = await api.exportReport(id)
      const blob = new Blob([md], { type: 'text/markdown' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a'); a.href = url; a.download = `audit-${id}.md`; a.click()
      URL.revokeObjectURL(url)
    } catch (e: any) { alert(e.message) }
  }

  const handleExportSarif = async () => {
    if (!id) return
    try {
      const sarif = await api.exportSarif(id)
      const blob = new Blob([sarif], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a'); a.href = url; a.download = `audit-${id}.sarif.json`; a.click()
      URL.revokeObjectURL(url)
    } catch (e: any) { alert(e.message) }
  }

  const tabs = [
    { key: 'overview' as const, icon: <Layers className="w-4 h-4" />, label: t('audit.overview') },
    { key: 'findings' as const, icon: <Bug className="w-4 h-4" />, label: `${t('audit.findingsTab')} (${findings.length})` },
    { key: 'logs' as const, icon: <Terminal className="w-4 h-4" />, label: `${t('audit.logsTab')} (${logs.length})` },
    { key: 'report' as const, icon: <FileText className="w-4 h-4" />, label: t('audit.report') },
  ]

  return (
    <div className="flex flex-col min-h-[calc(100vh-0px)]">
      {/* Scrollable content area */}
      <div className="flex-1 overflow-auto p-8 pb-20 max-w-7xl">
        {/* Back + Header */}
        <button onClick={() => navigate(-1)} className="flex items-center gap-1 text-text-muted hover:text-text text-sm mb-4 transition-colors">
          <ArrowLeft className="w-4 h-4" /> {t('audit.back')}
        </button>

        <div className="mb-6">
          <div className="flex items-center gap-3 flex-wrap">
            <h1 className="text-2xl font-bold">{t('audit.reportTitle')}</h1>
            <span className={`px-2.5 py-0.5 text-xs font-semibold rounded-full border ${
              isRunning ? 'bg-accent/10 text-accent border-accent/30' :
              audit.status === 'completed' ? 'bg-green-500/10 text-green-500 border-green-500/30' :
              'bg-severity-high/10 text-severity-high border-severity-high/30'
            }`}>
              {isRunning && <span className="inline-block w-1.5 h-1.5 rounded-full animate-pulse mr-1.5" style={{ background: '#6366f1' }} />}
              {STATUS_LABELS[audit.status] || audit.status}
            </span>
          </div>
          <div className="flex items-center gap-4 mt-2 text-text-muted text-sm flex-wrap">
            <span className="flex items-center gap-1"><Clock className="w-3.5 h-3.5" /> {audit.turns_completed} {t('audit.turns')}</span>
            <span className="flex items-center gap-1"><Terminal className="w-3.5 h-3.5" /> {audit.total_tool_calls} {t('audit.toolCalls')}</span>
            <span>· {(audit.total_tokens / 1000).toFixed(1)}K tokens</span>
            <span>· {audit.llm_provider}</span>
          </div>
        </div>

        {/* Pipeline visualizer */}
        <div className="mb-6">
          <PipelineVisualizer audit={audit} />
        </div>

        {/* Agent orchestration */}
        <div className="mb-6">
          <AgentOrchestration audit={audit} />
        </div>

        {/* Action bar */}
        <div className="flex items-center gap-2 mb-4 flex-wrap">
          {audit.status === 'running' && (
            <button onClick={handleAbort} disabled={actionLoading}
              className="flex items-center gap-1.5 px-3 py-1.5 text-sm border border-severity-high/30 text-severity-high rounded-lg hover:bg-severity-high/10 disabled:opacity-50 transition-colors">
              <StopCircle className="w-4 h-4" /> {actionLoading ? t('audit.aborting') : t('audit.abort')}
            </button>
          )}
          {(audit.status === 'aborted' || audit.status === 'failed') && (
            <button onClick={handleResume} disabled={actionLoading}
              className="flex items-center gap-1.5 px-3 py-1.5 text-sm border border-accent/30 text-accent rounded-lg hover:bg-accent/10 disabled:opacity-50 transition-colors">
              <PlayCircle className="w-4 h-4" /> {actionLoading ? t('audit.resuming') : t('audit.resume')}
            </button>
          )}
          <button onClick={handleExportMd}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm border border-border text-text-muted rounded-lg hover:text-text hover:bg-bg-hover transition-colors">
            <Download className="w-4 h-4" /> {t('audit.exportMd')}
          </button>
          <button onClick={handleExportSarif}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm border border-border text-text-muted rounded-lg hover:text-text hover:bg-bg-hover transition-colors">
            <ShieldCheck className="w-4 h-4" /> {t('audit.exportSarif')}
          </button>
        </div>

        {/* Tabs */}
        <div className="flex gap-0 mb-0 border-b border-border">
          {tabs.map(tb => (
            <button key={tb.key} onClick={() => setTab(tb.key)}
              className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
                tab === tb.key ? 'border-accent text-text' : 'border-transparent text-text-muted hover:text-text'
              }`}>
              {tb.icon} {tb.label}
            </button>
          ))}
        </div>

        {/* Tab content */}
        <div className="bg-bg-card border border-t-0 border-border rounded-b-xl p-5">
          {tab === 'overview' && <OverviewTab audit={audit} findings={findings} />}
          {tab === 'findings' && <FindingsTable findings={findings} isRunning={isRunning} />}
          {tab === 'logs' && <LogsTab logs={logs} isRunning={isRunning} />}
          {tab === 'report' && <ReportTab audit={audit} findings={findings} />}
        </div>
      </div>

      {/* Sticky bottom status bar */}
      <StatusBar audit={audit} />
    </div>
  )
}

/* ── Overview Tab ────────────────────────────────────────────── */

function OverviewTab({ audit, findings }: { audit: Audit; findings: Finding[] }) {
  const { t } = useI18n()
  const sevCount: Record<string, number> = { CRITICAL: 0, HIGH: 0, MEDIUM: 0, LOW: 0 }
  findings.forEach(f => { sevCount[f.severity] = (sevCount[f.severity] || 0) + 1 })
  const maxSev = Math.max(...Object.values(sevCount), 1)

  const typeCount: Record<string, number> = {}
  findings.forEach(f => { typeCount[f.vulnerability_type] = (typeCount[f.vulnerability_type] || 0) + 1 })
  const topTypes = Object.entries(typeCount).sort((a, b) => b[1] - a[1]).slice(0, 5)

  return (
    <div className="space-y-6">
      {/* Summary cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          { label: t('audit.findings'), value: findings.length, color: 'text-severity-high', bg: 'bg-severity-high/5' },
          { label: t('audit.confirmed'), value: findings.filter(f => f.confidence === 'HIGH').length, color: 'text-green-500', bg: 'bg-green-500/5' },
          { label: t('audit.coverage'), value: audit.covered_files?.length || 0, color: 'text-accent', bg: 'bg-accent/5' },
          { label: 'Tokens', value: `${(audit.total_tokens / 1000).toFixed(1)}K`, color: 'text-purple-400', bg: 'bg-purple-500/5' },
        ].map(c => (
          <div key={c.label} className={`${c.bg} border border-border rounded-xl p-4`}>
            <div className={`text-2xl font-bold ${c.color}`}>{c.value}</div>
            <div className="text-xs text-text-muted mt-1">{c.label}</div>
          </div>
        ))}
      </div>

      {/* Severity distribution */}
      <div>
        <h4 className="text-sm font-semibold mb-3">{t('dashboard.severityDist')}</h4>
        <div className="space-y-2">
          {Object.entries(sevCount).map(([sev, count]) => (
            <div key={sev} className="flex items-center gap-3">
              <span className="flex items-center gap-1.5 w-20 text-xs">
                <span className="w-2 h-2 rounded-full" style={{ background: SEVERITY_DOT[sev] }} />
                {sev}
              </span>
              <div className="flex-1 h-2.5 bg-bg rounded-full overflow-hidden">
                <div className="h-full rounded-full transition-all duration-500"
                  style={{ width: `${(count / maxSev) * 100}%`, background: SEVERITY_DOT[sev] }} />
              </div>
              <span className="text-xs font-mono font-bold w-8 text-right" style={{ color: SEVERITY_DOT[sev] }}>{count}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Top vulnerability types */}
      {topTypes.length > 0 && (
        <div>
          <h4 className="text-sm font-semibold mb-3">Top Vulnerability Types</h4>
          <div className="flex gap-2 flex-wrap">
            {topTypes.map(([type, count]) => (
              <span key={type} className="px-3 py-1.5 bg-bg border border-border rounded-lg text-xs">
                <span className="text-text-muted">{type.replace(/_/g, ' ')}</span>
                <span className="ml-2 font-bold text-accent">{count}</span>
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

/* ── Logs Tab ────────────────────────────────────────────────── */

function LogsTab({ logs, isRunning }: { logs: AuditLog[]; isRunning: boolean }) {
  const { t } = useI18n()
  if (logs.length === 0) {
    return <p className="text-text-muted text-sm py-10 text-center">{t('audit.noLogs')}</p>
  }
  return (
    <div className="space-y-1 font-mono text-xs max-h-[600px] overflow-y-auto">
      {logs.map(log => (
        <div key={log.id} className="flex items-start gap-2 p-2 hover:bg-bg-hover/30 rounded transition-colors">
          <span className="text-text-dim w-8 flex-shrink-0">T{log.turn}</span>
          <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold flex-shrink-0 ${
            log.role === 'assistant' ? 'bg-accent/10 text-accent' :
            log.role === 'tool' ? 'bg-bg-hover text-text-muted' : 'text-text-muted'
          }`}>{log.role}</span>
          {log.tool_name && <span className="text-severity-medium flex-shrink-0">→ {log.tool_name}</span>}
          <span className="text-text-muted truncate">{log.content?.slice(0, 120)}</span>
          {log.tokens_used > 0 && <span className="text-text-dim flex-shrink-0">{log.tokens_used}t</span>}
        </div>
      ))}
    </div>
  )
}

/* ── Report Tab ──────────────────────────────────────────────── */

function ReportTab({ audit, findings }: { audit: Audit; findings: Finding[] }) {
  const [lang, setLang] = useState<'zh' | 'en'>('zh')

  const zhLabels: Record<string, string> = {
    SQL_Injection: 'SQL 注入', XSS: '跨站脚本(XSS)', SSRF: '服务端请求伪造',
    Path_Traversal: '路径遍历', Deserialization: '反序列化', Authentication_Bypass: '认证绕过',
    RCE: '远程代码执行', Crypto_Issue: '加密问题', Info_Disclosure: '信息泄露',
    Hardcoded_Secret: '硬编码密钥', Business_Logic: '业务逻辑', Race_Condition: '竞态条件',
  }

  const severityLabels: Record<string, Record<string, string>> = {
    zh: { CRITICAL: '严重', HIGH: '高危', MEDIUM: '中危', LOW: '低危' },
    en: { CRITICAL: 'CRITICAL', HIGH: 'HIGH', MEDIUM: 'MEDIUM', LOW: 'LOW' },
  }

  const title = lang === 'zh' ? '代码安全审计报告' : 'Code Security Audit Report'
  const date = new Date().toISOString().split('T')[0]

  return (
    <div>
      {/* Print-only report preview */}
      <div className="mb-4 flex items-center gap-2">
        <button onClick={() => setLang(l => l === 'zh' ? 'en' : 'zh')}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs border border-border rounded-lg hover:bg-bg-hover transition-colors">
          <Globe className="w-3.5 h-3.5" /> {lang === 'zh' ? 'Switch to English' : '切换到中文'}
        </button>
        <button onClick={() => window.print()}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs border border-border rounded-lg hover:bg-bg-hover transition-colors">
          <Printer className="w-3.5 h-3.5" /> {lang === 'zh' ? '打印报告' : 'Print Report'}
        </button>
      </div>

      <div className="report-preview bg-white text-gray-900 rounded-xl p-8 print:shadow-none" id="printable-report">
        {/* Report Header */}
        <div className="border-b-2 border-gray-200 pb-6 mb-6">
          <h1 className="text-2xl font-bold mb-2">{title}</h1>
          <div className="grid grid-cols-2 gap-2 text-sm text-gray-600">
            <div>{lang === 'zh' ? '项目名称' : 'Project'}: {audit.id}</div>
            <div>{lang === 'zh' ? '审计模式' : 'Mode'}: {audit.mode}</div>
            <div>{lang === 'zh' ? 'LLM 模型' : 'LLM'}: {audit.llm_provider}</div>
            <div>{lang === 'zh' ? '日期' : 'Date'}: {date}</div>
            <div>{lang === 'zh' ? '发现漏洞' : 'Findings'}: {findings.length}</div>
            <div>{lang === 'zh' ? '消耗 Tokens' : 'Tokens'}: {(audit.total_tokens / 1000).toFixed(1)}K</div>
          </div>
        </div>

        {/* Summary */}
        <div className="mb-6">
          <h2 className="text-lg font-bold mb-3">{lang === 'zh' ? '摘要' : 'Executive Summary'}</h2>
          <p className="text-gray-700 text-sm">
            {lang === 'zh'
              ? `本次审计共发现 ${findings.length} 个安全漏洞，涉及 ${new Set(findings.map(f => f.vulnerability_type)).size} 种漏洞类型。`
              : `This audit identified ${findings.length} security vulnerabilities across ${new Set(findings.map(f => f.vulnerability_type)).size} vulnerability types.`
            }
          </p>
        </div>

        {/* Findings table */}
        <div>
          <h2 className="text-lg font-bold mb-3">{lang === 'zh' ? '漏洞详情' : 'Findings Detail'}</h2>
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="border-b-2 border-gray-300 text-left">
                <th className="py-2 px-3 w-12">#</th>
                <th className="py-2 px-3">{lang === 'zh' ? '严重级别' : 'Severity'}</th>
                <th className="py-2 px-3">{lang === 'zh' ? '类型' : 'Type'}</th>
                <th className="py-2 px-3">{lang === 'zh' ? '标题' : 'Title'}</th>
                <th className="py-2 px-3">{lang === 'zh' ? '文件位置' : 'Location'}</th>
              </tr>
            </thead>
            <tbody>
              {findings.map((f, i) => (
                <tr key={f.id} className="border-b border-gray-200">
                  <td className="py-2 px-3 text-gray-500">{i + 1}</td>
                  <td className="py-2 px-3">
                    <span className="font-bold" style={{ color: SEVERITY_DOT[f.severity] }}>
                      {severityLabels[lang][f.severity] || f.severity}
                    </span>
                  </td>
                  <td className="py-2 px-3">
                    {lang === 'zh' ? (zhLabels[f.vulnerability_type] || f.vulnerability_type) : f.vulnerability_type.replace(/_/g, ' ')}
                  </td>
                  <td className="py-2 px-3">{f.title}</td>
                  <td className="py-2 px-3 text-gray-600 font-mono text-xs">{f.file_path}:{f.line_start}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Footer */}
        <div className="mt-8 pt-4 border-t border-gray-200 text-xs text-gray-400 text-center">
          {lang === 'zh' ? '本报告由 CodeAudit AI Agent 自动生成' : 'Generated by CodeAudit AI Agent'} · {date}
        </div>
      </div>
    </div>
  )
}
