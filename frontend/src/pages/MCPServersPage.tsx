
import { useState, useEffect } from 'react'
import { Server, Plug, Activity, Zap, Shield, CheckCircle2, XCircle, RefreshCw, Globe, KeyRound, Plus, Trash2, X } from 'lucide-react'
import { api } from '../services/api'
import type { MCPServerInfo, MCPTestResult, MCPStats } from '../types'
import { useI18n } from '../i18n'

export default function MCPServersPage() {
  const { t } = useI18n()
  const [servers, setServers] = useState<MCPServerInfo[]>([])
  const [stats, setStats] = useState<MCPStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [testing, setTesting] = useState<string | null>(null)
  const [testResults, setTestResults] = useState<Record<string, MCPTestResult>>({})
  const [showAdd, setShowAdd] = useState(false)
  const [addForm, setAddForm] = useState({ name: '', url: '', headers: '', description: '', timeout: 30 })
  const [addError, setAddError] = useState('')
  const [adding, setAdding] = useState(false)

  const load = async () => {
    try {
      const [s, st] = await Promise.all([api.listMCPServers(), api.getMCPStats()])
      setServers(s.servers || [])
      setStats(st)
    } catch (_) {} finally { setLoading(false) }
  }

  useEffect(() => { load() }, [])

  const handleTest = async (name: string) => {
    setTesting(name)
    try {
      const result = await api.testMCPServer(name)
      setTestResults(prev => ({ ...prev, [name]: result }))
    } catch (e: any) {
      setTestResults(prev => ({ ...prev, [name]: { status: 'failed', latency_ms: 0, error: e.message } }))
    } finally { setTesting(null) }
  }

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault()
    setAddError('')
    setAdding(true)
    try {
      let headers: Record<string, string> = {}
      if (addForm.headers.trim()) {
        try { headers = JSON.parse(addForm.headers) } catch { throw new Error('Headers must be valid JSON') }
      }
      await api.createMCPServer({
        name: addForm.name,
        url: addForm.url,
        headers,
        timeout: addForm.timeout,
        description: addForm.description,
      })
      setShowAdd(false)
      setAddForm({ name: '', url: '', headers: '', description: '', timeout: 30 })
      await load()
      alert(t('mcp.addSuccess'))
    } catch (err: any) { setAddError(err.message || 'Failed') }
    finally { setAdding(false) }
  }

  const handleDelete = async (s: MCPServerInfo) => {
    if (!confirm(t('mcp.deleteConfirm').replace('{name}', s.name))) return
    try {
      await api.deleteMCPServer(s.name)
      await load()
      alert(t('mcp.deleteSuccess'))
    } catch (err: any) { alert(err.message || 'Failed') }
  }

  return (
    <div className="p-8 max-w-5xl">
      <h1 className="text-2xl font-bold flex items-center gap-2 mb-1">
        <Server className="w-6 h-6 text-accent" /> MCP
      </h1>
      <div className="flex items-center justify-between mb-6 flex-wrap gap-3">
        <p className="text-text-muted text-sm">{t('mcp.subtitle')}</p>
        <button
          onClick={() => setShowAdd(true)}
          className="flex items-center gap-1.5 px-3 py-2 bg-accent hover:bg-accent-hover rounded-lg text-sm font-medium transition-colors"
        >
          <Plus className="w-4 h-4" /> {t('mcp.add')}
        </button>
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        <StatCard icon={<Server className="w-4 h-4" />} label={t('mcp.configured')} value={stats?.configured_servers ?? 0} color="#6366f1" />
        <StatCard icon={<Plug className="w-4 h-4" />} label={t('mcp.enabled')} value={stats?.enabled_servers ?? 0} color="#10b981" />
        <StatCard icon={<Zap className="w-4 h-4" />} label={t('mcp.tools')} value={stats?.registered_tools ?? 0} color="#8b5cf6" />
        <StatCard icon={<Activity className="w-4 h-4" />} label={t('mcp.calls')} value={stats?.calls_total ?? 0} color="#f59e0b" />
      </div>

      {loading ? (
        <p className="text-text-muted text-sm py-10 text-center">{t('common.loading')}</p>
      ) : servers.length === 0 ? (
        <div className="text-center py-20 text-text-muted">
          <Server className="w-12 h-12 mx-auto mb-3 opacity-40" />
          <p>{t('mcp.empty')}</p>
        </div>
      ) : (
        <div className="space-y-4">
          {servers.map(s => {
            const tr = testResults[s.name]
            const statusOk = tr?.status === 'connected'
            return (
              <div key={s.name} className="bg-bg-card border border-border rounded-xl p-5">
                <div className="flex items-start justify-between flex-wrap gap-3">
                  <div className="flex items-center gap-3">
                    <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${s.enabled ? 'bg-accent/10' : 'bg-bg-hover'}`}>
                      <Server className={`w-5 h-5 ${s.enabled ? 'text-accent' : 'text-text-dim'}`} />
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-semibold">{s.name}</span>
                        <span className={`flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded ${
                          tr ? (statusOk ? 'bg-green-500/10 text-green-500' : 'bg-severity-high/10 text-severity-high') : 'bg-bg-hover text-text-muted'
                        }`}>
                          {tr ? (statusOk ? <><CheckCircle2 className="w-3 h-3" /> {t('mcp.connected')}</> : <><XCircle className="w-3 h-3" /> {t('mcp.failed')}</>) : <>{s.enabled ? <CheckCircle2 className="w-3 h-3" /> : <XCircle className="w-3 h-3" />} {s.enabled ? t('mcp.enabled') : t('mcp.disabled')}</>}
                        </span>
                      </div>
                      <div className="text-xs text-text-muted font-mono mt-0.5">{s.url}</div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {tr && (
                      <span className="text-[11px] text-text-muted flex items-center gap-1">
                        <Zap className="w-3 h-3" /> {tr.latency_ms}ms
                        {tr.tools_count !== undefined && <> · {tr.tools_count} {t('mcp.tools')}</>}
                      </span>
                    )}
                    <button
                      onClick={() => handleTest(s.name)}
                      disabled={testing === s.name}
                      className="flex items-center gap-1.5 px-3 py-1.5 text-xs border border-border rounded-lg hover:bg-bg-hover disabled:opacity-50 transition-colors"
                    >
                      <RefreshCw className={`w-3.5 h-3.5 ${testing === s.name ? 'animate-spin' : ''}`} />
                      {testing === s.name ? t('mcp.testing') : t('mcp.test')}
                    </button>
                    <button
                      onClick={() => handleDelete(s)}
                      className="p-1.5 text-text-dim hover:text-severity-high transition-colors"
                      title={t('mcp.deleteConfirm').replace('{name}', s.name)}
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>

                {/* Description + auth badge */}
                <div className="mt-3 flex items-center gap-3 text-[11px] text-text-muted">
                  {s.description && <span className="flex-1">{s.description}</span>}
                  <span className={`flex items-center gap-1 ${s.has_auth ? 'text-green-500' : 'text-text-dim'}`}>
                    <KeyRound className="w-3 h-3" />
                    {s.has_auth ? t('mcp.authEnabled') : t('mcp.noAuth')}
                  </span>
                  <span className="flex items-center gap-1 text-text-dim">
                    <Globe className="w-3 h-3" /> {s.timeout}s
                  </span>
                </div>

                {/* Tool list when tested */}
                {tr?.status === 'connected' && tr.tools && tr.tools.length > 0 && (
                  <div className="mt-3 pt-3 border-t border-border/60">
                    <div className="text-[10px] font-semibold uppercase tracking-wider text-text-dim mb-2 flex items-center gap-1">
                      <Shield className="w-3 h-3" /> {t('mcp.toolList')}
                    </div>
                    <div className="flex flex-wrap gap-1.5">
                      {tr.tools.map(toolName => (
                        <span key={toolName} className="px-2 py-0.5 bg-bg border border-border rounded text-[10px] font-mono text-text-muted">
                          {toolName}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {/* Error */}
                {tr?.status === 'failed' && tr.error && (
                  <div className="mt-3 pt-3 border-t border-border/60">
                    <p className="text-[11px] text-severity-high">{t('mcp.error')}: {tr.error}</p>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}

      {/* Add server modal */}
      {showAdd && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/50" onClick={() => setShowAdd(false)} />
          <form onSubmit={handleAdd} className="relative w-[520px] max-w-[92vw] bg-bg-card border border-border rounded-xl p-6 space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold flex items-center gap-2">
                <Plus className="w-5 h-5 text-accent" /> {t('mcp.addTitle')}
              </h2>
              <button type="button" onClick={() => setShowAdd(false)} className="text-text-muted hover:text-text">
                <X className="w-4 h-4" />
              </button>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-sm font-medium mb-1.5">{t('mcp.name')}</label>
                <input
                  value={addForm.name}
                  onChange={e => setAddForm({ ...addForm, name: e.target.value })}
                  placeholder={t('mcp.namePlaceholder')}
                  className="w-full px-3 py-2 bg-bg border border-border rounded-lg text-sm font-mono focus:outline-none focus:border-accent"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1.5">Timeout (s)</label>
                <input
                  type="number"
                  min={1}
                  max={300}
                  value={addForm.timeout}
                  onChange={e => setAddForm({ ...addForm, timeout: Number(e.target.value) })}
                  className="w-full px-3 py-2 bg-bg border border-border rounded-lg text-sm focus:outline-none focus:border-accent"
                />
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium mb-1.5">{t('mcp.url')}</label>
              <input
                value={addForm.url}
                onChange={e => setAddForm({ ...addForm, url: e.target.value })}
                placeholder={t('mcp.urlPlaceholder')}
                className="w-full px-3 py-2 bg-bg border border-border rounded-lg text-sm font-mono focus:outline-none focus:border-accent"
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1.5">{t('mcp.headers')}</label>
              <textarea
                value={addForm.headers}
                onChange={e => setAddForm({ ...addForm, headers: e.target.value })}
                placeholder={t('mcp.headersPlaceholder')}
                rows={3}
                className="w-full px-3 py-2 bg-bg border border-border rounded-lg text-sm font-mono focus:outline-none focus:border-accent resize-y"
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1.5">{t('projects.desc')}</label>
              <input
                value={addForm.description}
                onChange={e => setAddForm({ ...addForm, description: e.target.value })}
                placeholder={t('mcp.descriptionPlaceholder')}
                className="w-full px-3 py-2 bg-bg border border-border rounded-lg text-sm focus:outline-none focus:border-accent"
              />
            </div>
            {addError && <p className="text-severity-high text-sm">{addError}</p>}
            <div className="flex gap-2 justify-end">
              <button type="button" onClick={() => setShowAdd(false)}
                className="px-4 py-2 border border-border rounded-lg text-sm hover:bg-bg-hover transition-colors">
                {t('projects.cancel')}
              </button>
              <button type="submit" disabled={adding}
                className="px-4 py-2 bg-accent hover:bg-accent-hover rounded-lg text-sm font-medium disabled:opacity-50 transition-colors">
                {adding ? t('common.loading') : t('mcp.addBtn')}
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  )
}

function StatCard({ icon, label, value, color }: { icon: React.ReactNode; label: string; value: number; color: string }) {
  return (
    <div className="bg-bg-card border border-border rounded-xl p-4">
      <div className="mb-2" style={{ color }}>{icon}</div>
      <div className="text-2xl font-bold">{value}</div>
      <div className="text-text-muted text-xs mt-1">{label}</div>
    </div>
  )
}
