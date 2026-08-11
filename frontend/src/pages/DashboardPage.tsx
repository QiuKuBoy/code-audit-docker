
import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { Folder, Bug, Activity, Zap, TrendingUp, Cpu, Server, Layers, GitBranch, Clock } from 'lucide-react'
import { api } from '../services/api'
import type { DashboardStats } from '../types'
import { useI18n } from '../i18n'

const SEVERITY_COLORS: Record<string, string> = {
  CRITICAL: '#ef4444', HIGH: '#f97316', MEDIUM: '#eab308', LOW: '#3b82f6',
}

const STATUS_LABELS: Record<string, string> = {
  running: '运行中', completed: '已完成', failed: '失败',
  aborted: '已中止', pending: '等待中', max_turns: '达轮次上限',
}

const MODE_LABELS: Record<string, string> = {
  quick: '快速扫描', smart: '智能审计', comprehensive: '综合审计',
}

const SEVERITY_LABELS: Record<string, string> = {
  CRITICAL: '严重', HIGH: '高危', MEDIUM: '中危', LOW: '低危',
}

export default function DashboardPage() {
  const { t } = useI18n()
  const [stats, setStats] = useState<DashboardStats | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.getDashboardStats().then(setStats).catch(() => {}).finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="p-8 text-text-muted">{t('common.loading')}</div>
  if (!stats) return <div className="p-8 text-text-muted">{t('dashboard.noData')}</div>

  const severityData = [
    { label: t('dashboard.critical'), value: stats.findings_by_severity['CRITICAL'] || 0, color: SEVERITY_COLORS.CRITICAL },
    { label: t('dashboard.high'), value: stats.findings_by_severity['HIGH'] || 0, color: SEVERITY_COLORS.HIGH },
    { label: t('dashboard.medium'), value: stats.findings_by_severity['MEDIUM'] || 0, color: SEVERITY_COLORS.MEDIUM },
    { label: t('dashboard.low'), value: stats.findings_by_severity['LOW'] || 0, color: SEVERITY_COLORS.LOW },
  ]
  const maxSev = Math.max(...severityData.map(d => d.value), 1)
  const typeEntries = Object.entries(stats.findings_by_type).sort((a, b) => b[1] - a[1]).slice(0, 8)
  const maxType = Math.max(...typeEntries.map(([, v]) => v), 1)
  const timelineMax = Math.max(...stats.severity_timeline.map(e => e.critical + e.high + e.medium + e.low), 1)

  return (
    <div className="p-8 max-w-7xl pb-20">
      <h1 className="text-2xl font-bold mb-1">{t('dashboard.title')}</h1>
      <p className="text-text-muted text-sm mb-6">{t('dashboard.subtitle')}</p>

      {/* Stat cards - top row */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-6">
        <StatCard icon={<Folder className="w-5 h-5" />} label={t('dashboard.totalProjects')} value={stats.total_projects} color="#6366f1" />
        <StatCard icon={<Activity className="w-5 h-5" />} label={t('dashboard.totalAudits')} value={stats.total_audits} color="#8b5cf6" />
        <StatCard icon={<Bug className="w-5 h-5" />} label={t('dashboard.totalFindings')} value={stats.total_findings} color="#ef4444" />
        <StatCard icon={<Zap className="w-5 h-5" />} label={t('dashboard.totalTokens')} value={formatNum(stats.total_tokens)} color="#a855f7" />
        <StatCard icon={<TrendingUp className="w-5 h-5" />} label={t('dashboard.totalToolCalls')} value={stats.total_tool_calls} color="#10b981" />
      </div>

      {/* Agent & System Health */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        <HealthCard icon={<Cpu className="w-4 h-4" />} label={t('dash.agentHealth')} status="ok" statusText="正常" color="#10b981" />
        <HealthCard icon={<Server className="w-4 h-4" />} label={t('dash.mcpServers')} status="ok" statusText="1 已连接" color="#6366f1" />
        <HealthCard icon={<GitBranch className="w-4 h-4" />} label={t('dash.activeSessions')} status="ok" statusText={`共 ${stats.total_audits} 次`} color="#8b5cf6" />
        <HealthCard icon={<Layers className="w-4 h-4" />} label={t('dash.coverageRate')} status="ok" statusText="--" color="#06b6d4" />
      </div>

      {/* Orchestration Pipeline Overview */}
      <div className="bg-bg-card border border-border rounded-xl p-5 mb-6">
        <h3 className="text-sm font-semibold mb-4 flex items-center gap-2">
          <GitBranch className="w-4 h-4 text-accent" /> {t('audit.orchestration')}
        </h3>
        <div className="flex items-center gap-1 flex-wrap">
          {[
            { s: '侦察', c: '#6366f1', d: '识别项目结构与入口点' },
            { s: '扫描', c: '#8b5cf6', d: 'SAST + SCA + 自定义规则' },
            { s: '研判', c: '#f59e0b', d: '过滤误报' },
            { s: '深挖', c: '#10b981', d: '按漏洞类型深度分析' },
            { s: '验证', c: '#06b6d4', d: 'PoC 验证 + 对抗审查' },
            { s: '报告', c: '#ec4899', d: 'MD / SARIF / HTML 导出' },
          ].map((stage, i) => (
            <div key={stage.s} className="flex items-center flex-1 min-w-[100px]">
              <div className="flex flex-col items-center border-2 rounded-xl px-3 py-2 bg-bg w-full" style={{ borderColor: stage.c + '40' }}>
                <span className="text-[10px] font-bold" style={{ color: stage.c }}>{stage.s}</span>
                <span className="text-[9px] text-text-dim mt-0.5 text-center leading-tight">{stage.d}</span>
              </div>
              {i < 5 && <span className="text-text-dim text-xs mx-0.5">→</span>}
            </div>
          ))}
        </div>
      </div>

      {/* Severity + Type */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
        <div className="bg-bg-card border border-border rounded-xl p-5">
          <h3 className="text-sm font-semibold mb-4">{t('dashboard.severityDist')}</h3>
          <div className="space-y-3">
            {severityData.map(d => (
              <div key={d.label}>
                <div className="flex items-center justify-between text-xs mb-1.5">
                  <span className="text-text-muted">{d.label}</span>
                  <span className="font-mono font-bold" style={{ color: d.color }}>{d.value}</span>
                </div>
                <div className="h-2.5 bg-bg rounded-full overflow-hidden">
                  <div className="h-full rounded-full transition-all duration-700 ease-out" style={{ width: `${(d.value / maxSev) * 100}%`, background: d.color }} />
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="bg-bg-card border border-border rounded-xl p-5">
          <h3 className="text-sm font-semibold mb-4">{t('dashboard.typeDist')}</h3>
          {typeEntries.length === 0 ? (
            <p className="text-text-muted text-sm">{t('dashboard.noData')}</p>
          ) : (
            <div className="space-y-2.5">
              {typeEntries.map(([type, count]) => (
                <div key={type} className="flex items-center gap-2">
                  <span className="text-xs text-text-muted w-36 truncate">{type.replace(/_/g, ' ')}</span>
                  <div className="flex-1 h-2 bg-bg rounded-full overflow-hidden">
                    <div className="h-full bg-accent/60 rounded-full transition-all duration-500" style={{ width: `${(count / maxType) * 100}%` }} />
                  </div>
                  <span className="text-xs font-mono w-7 text-right">{count}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Timeline */}
      {stats.severity_timeline.length > 0 && (
        <div className="bg-bg-card border border-border rounded-xl p-5 mb-6">
          <h3 className="text-sm font-semibold mb-4">{t('dash.auditTrend')}</h3>
          <div className="flex items-end gap-1 h-40">
            {stats.severity_timeline.map((entry, i) => {
              const total = entry.critical + entry.high + entry.medium + entry.low
              const h = Math.max((total / timelineMax) * 100, total > 0 ? 2 : 0)
              return (
                <div key={i} className="flex-1 flex flex-col justify-end items-center group relative" style={{ height: '100%' }}>
                  <div className="w-full flex flex-col-reverse rounded-t overflow-hidden" style={{ height: `${h}%`, minHeight: total > 0 ? '4px' : '0' }}>
                    {entry.low > 0 && <div style={{ height: `${(entry.low / total) * 100}%`, background: SEVERITY_COLORS.LOW }} />}
                    {entry.medium > 0 && <div style={{ height: `${(entry.medium / total) * 100}%`, background: SEVERITY_COLORS.MEDIUM }} />}
                    {entry.high > 0 && <div style={{ height: `${(entry.high / total) * 100}%`, background: SEVERITY_COLORS.HIGH }} />}
                    {entry.critical > 0 && <div style={{ height: `${(entry.critical / total) * 100}%`, background: SEVERITY_COLORS.CRITICAL }} />}
                  </div>
                </div>
              )
            })}
          </div>
          <div className="flex gap-4 mt-3 text-xs text-text-muted">
            {Object.entries(SEVERITY_COLORS).map(([k, c]) => (
              <span key={k} className="flex items-center gap-1"><span className="w-2 h-2 rounded-full" style={{ background: c }} />{k}</span>
            ))}
          </div>
        </div>
      )}

      {/* Recent audits */}
      <div className="bg-bg-card border border-border rounded-xl p-5">
        <h3 className="text-sm font-semibold mb-4">{t('dashboard.recentAudits')}</h3>
        {stats.recent_audits.length === 0 ? (
          <p className="text-text-muted text-sm">{t('dashboard.noData')}</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-text-dim text-[11px] uppercase tracking-wider">
                  <th className="text-left p-3">项目</th>
                  <th className="text-left p-3">模式</th>
                  <th className="text-left p-3">状态</th>
                  <th className="text-left p-3">漏洞数</th>
                  <th className="text-left p-3">轮次</th>
                  <th className="text-left p-3">Tokens</th>
                </tr>
              </thead>
              <tbody>
                {stats.recent_audits.map(a => (
                  <tr key={a.id} className="border-b border-border/50 hover:bg-bg-hover/30 transition-colors">
                    <td className="p-3">
                      <Link to={`/audits/${a.id}`} className="text-accent hover:underline font-medium">{a.project_name}</Link>
                    </td>
                    <td className="p-3 text-text-muted">{MODE_LABELS[a.mode] || a.mode}</td>
                    <td className="p-3">
                      <span className={`inline-flex items-center gap-1 text-xs font-medium ${a.status === 'completed' ? 'text-green-500' : a.status === 'running' ? 'text-accent' : 'text-text-muted'}`}>
                        <span className="w-1.5 h-1.5 rounded-full" style={{ background: a.status === 'completed' ? '#22c55e' : a.status === 'running' ? '#6366f1' : '#71717a' }} />
                        {STATUS_LABELS[a.status] || a.status}
                      </span>
                    </td>
                    <td className="p-3 font-mono">{a.findings_count}</td>
                    <td className="p-3 text-text-muted">{a.turns}</td>
                    <td className="p-3 text-text-dim font-mono">{formatNum(a.tokens)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Bottom status bar */}
      <div className="status-bar">
        <div className="flex items-center gap-6">
          <StatusDot label="模型" value="deepseek-v4-flash" color="#10b981" />
          <StatusDot label="MCP" value="src-wiki" color="#6366f1" />
          <StatusDot label="技能包" value="14 个已加载" color="#8b5cf6" />
        </div>
        <div className="flex items-center gap-4 text-xs text-text-dim">
          <span className="flex items-center gap-1"><Clock className="w-3 h-3" /> Code Audit v1.1.0</span>
          <span>路 MCP 已启用 路 专精 Agent 就绪</span>
        </div>
      </div>
    </div>
  )
}

function StatCard({ icon, label, value, color }: { icon: React.ReactNode; label: string; value: number | string; color: string }) {
  return (
    <div className="bg-bg-card border border-border rounded-xl p-4 hover:border-text-dim/50 transition-colors">
      <div className="mb-2" style={{ color }}>{icon}</div>
      <div className="text-2xl font-bold">{value}</div>
      <div className="text-text-muted text-xs mt-1">{label}</div>
    </div>
  )
}

function HealthCard({ icon, label, status, statusText, color }: { icon: React.ReactNode; label: string; status: string; statusText: string; color: string }) {
  return (
    <div className="bg-bg-card border border-border rounded-xl p-4">
      <div className="flex items-center justify-between mb-2">
        <span className="text-text-dim">{icon}</span>
        <span className="w-2 h-2 rounded-full" style={{ background: color }} />
      </div>
      <div className="text-sm font-medium">{label}</div>
      <div className="text-xs mt-1" style={{ color }}>{statusText}</div>
    </div>
  )
}

function StatusDot({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div className="flex items-center gap-1.5">
      <span className="w-2 h-2 rounded-full" style={{ background: color }} />
      <span className="text-[10px] text-text-dim uppercase">{label}:</span>
      <span className="text-xs">{value}</span>
    </div>
  )
}

function formatNum(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`
  return String(n)
}
