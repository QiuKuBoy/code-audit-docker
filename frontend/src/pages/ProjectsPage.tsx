
import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Folder, Plus, Trash2, ChevronRight, Cpu, Layers, Clock, CheckCircle2, RotateCcw, Archive, Upload, GitBranch, HardDrive } from 'lucide-react'
import { api } from '../services/api'
import type { Project, Audit, LLMProviderInfo, BatchAuditResult } from '../types'
import { useI18n } from '../i18n'

const PROVIDER_LABELS: Record<string, string> = {
  deepseek: 'DeepSeek', openai: 'OpenAI', anthropic: 'Claude',
  gemini: 'Gemini', baidu: 'ERNIE', doubao: 'Doubao',
  minimax: 'MiniMax', zhipu: 'GLM', qwen: 'Qwen', kimi: 'Kimi',
  siliconflow: 'SiliconFlow',
}

type ProjectStatus = 'all' | 'completed' | 'in_progress' | 'archived'
type SourceTab = 'local' | 'upload' | 'git'

function deriveStatus(audits: Audit[]): ProjectStatus {
  if (audits.length === 0) return 'archived'
  const latest = audits[0]
  if (latest.status === 'running' || latest.status === 'pending') return 'in_progress'
  if (latest.status === 'completed') return 'completed'
  return 'archived'
}

export default function ProjectsPage({ newMode }: { newMode?: boolean }) {
  const { t } = useI18n()
  const [projects, setProjects] = useState<(Project & { audits?: Audit[]; status?: ProjectStatus })[]>([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(!!newMode)
  const [form, setForm] = useState({ name: '', path: '', description: '', language: 'auto' })
  const [sourceTab, setSourceTab] = useState<SourceTab>('upload')
  const [zipFile, setZipFile] = useState<File | null>(null)
  const [gitUrl, setGitUrl] = useState('')
  const [autoStart, setAutoStart] = useState(true)
  const [auditMode, setAuditMode] = useState('smart')
  const [auditProvider, setAuditProvider] = useState('deepseek')
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const [filterTab, setFilterTab] = useState<ProjectStatus>('all')
  const navigate = useNavigate()

  const [batchMode, setBatchMode] = useState(false)
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [providers, setProviders] = useState<LLMProviderInfo[]>([])
  const [batchProvider, setBatchProvider] = useState('deepseek')
  const [batchLoading, setBatchLoading] = useState(false)
  const [batchResult, setBatchResult] = useState<BatchAuditResult | null>(null)

  const load = async () => {
    try {
      const [data, pv] = await Promise.all([api.getProjects(), api.getLLMProviders()])
      // Fetch latest audit status for each project
      const enriched = await Promise.all(data.map(async (p) => {
        try {
          const audits = await api.getProjectAudits(p.id)
          return { ...p, audits: audits as Audit[], status: deriveStatus(audits as Audit[]) }
        } catch { return { ...p, audits: [], status: 'archived' as ProjectStatus } }
      }))
      setProjects(enriched)
      setProviders(pv)
    } catch (_) {} finally { setLoading(false) }
  }

  useEffect(() => { load() }, [])

  const submit = async (e: React.FormEvent) => {
    e.preventDefault(); setError('')
    try {
      let project: Project
      const lang = form.language === 'auto' ? '' : form.language
      if (sourceTab === 'local') {
        project = await api.createProject({ ...form, language: form.language || 'auto' })
      } else if (sourceTab === 'upload') {
        if (!zipFile) { setError(t('projects.zipSelect')); return }
        setBusy(t('projects.uploading'))
        project = await api.uploadProject(zipFile, { name: form.name, description: form.description, language: lang })
      } else {
        if (!gitUrl.trim()) { setError(t('projects.gitUrl')); return }
        setBusy(t('projects.cloning'))
        project = await api.cloneProject({ url: gitUrl.trim(), name: form.name, description: form.description, language: lang })
      }
      setBusy('')
      // Upload / Git flows can start an audit right away
      if (autoStart && sourceTab !== 'local') {
        const isConfigured = providers.find(p => p.provider === auditProvider)?.configured
        if (!isConfigured) { alert(t('detail.noKeyGoSettings')); navigate(`/projects/${project.id}`); return }
        setBusy(t('projects.startingAudit'))
        const res = await api.createAudit({ project_id: project.id, mode: auditMode, llm_provider: auditProvider })
        navigate(`/audits/${res.audit_id}`)
        return
      }
      navigate(`/projects/${project.id}`)
    }
    catch (e: any) { setError(e.message) }
    finally { setBusy('') }
  }

  const remove = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation()
    if (!confirm(t('projects.delete'))) return
    await api.deleteProject(id); load()
  }

  const toggleSelect = (id: string) => {
    setSelected(prev => { const next = new Set(prev); next.has(id) ? next.delete(id) : next.add(id); return next })
  }

  const startBatch = async () => {
    if (selected.size === 0) return
    const isConfigured = providers.find(p => p.provider === batchProvider)?.configured
    if (!isConfigured) { alert(t('detail.noKeyGoSettings')); return }
    setBatchLoading(true)
    try {
      const result = await api.createBatchAudits({ project_ids: Array.from(selected), llm_provider: batchProvider })
      setBatchResult(result)
      if (result.started.length > 0) setTimeout(() => navigate(`/audits/${result.started[0]}`), 1500)
    } catch (e: any) { alert(e.message) } finally { setBatchLoading(false) }
  }

  const selectedProviderInfo = providers.find(p => p.provider === batchProvider)

  const filtered = filterTab === 'all' ? projects : projects.filter(p => p.status === filterTab)

  const tabs: { key: ProjectStatus; icon: React.ReactNode; label: string; count: number }[] = [
    { key: 'all', icon: <Folder className="w-4 h-4" />, label: t('projects.all'), count: projects.length },
    { key: 'completed', icon: <CheckCircle2 className="w-4 h-4" />, label: t('projects.completed'), count: projects.filter(p => p.status === 'completed').length },
    { key: 'in_progress', icon: <RotateCcw className="w-4 h-4" />, label: t('projects.inProgress'), count: projects.filter(p => p.status === 'in_progress').length },
    { key: 'archived', icon: <Archive className="w-4 h-4" />, label: t('projects.archived'), count: projects.filter(p => p.status === 'archived').length },
  ]

  const getStatusBadge = (status: ProjectStatus) => {
    const config: Record<string, { icon: React.ReactNode; color: string; bg: string; text: string }> = {
      completed: { icon: <CheckCircle2 className="w-3 h-3" />, color: 'text-green-500', bg: 'bg-green-500/10', text: t('projects.completed') },
      in_progress: { icon: <RotateCcw className="w-3 h-3 animate-spin" />, color: 'text-accent', bg: 'bg-accent/10', text: t('projects.inProgress') },
      archived: { icon: <Archive className="w-3 h-3" />, color: 'text-text-muted', bg: 'bg-bg-hover', text: t('projects.archived') },
    }
    const c = config[status] || config.archived
    return (
      <span className={`inline-flex items-center gap-1 px-2 py-0.5 text-[10px] font-medium rounded ${c.bg} ${c.color}`}>
        {c.icon} {c.text}
      </span>
    )
  }

  return (
    <div className="p-8 max-w-5xl">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">{t('projects.title')}</h1>
          <p className="text-text-muted text-sm mt-1">{t('projects.subtitle')}</p>
        </div>
        <div className="flex gap-2">
          {projects.length > 1 && (
            <button onClick={() => { setBatchMode(!batchMode); setSelected(new Set()); setBatchResult(null) }}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${batchMode ? 'bg-accent text-white' : 'border border-border hover:bg-bg-hover'}`}>
              <Layers className="w-4 h-4" /> {t('batch.title')}
            </button>
          )}
          <button onClick={() => setShowForm(!showForm)}
            className="flex items-center gap-2 px-4 py-2 bg-accent hover:bg-accent-hover rounded-lg text-sm font-medium transition-colors">
            <Plus className="w-4 h-4" /> {t('projects.new')}
          </button>
        </div>
      </div>

      {/* Batch audit panel */}
      {batchMode && (
        <div className="bg-bg-card border border-accent/30 rounded-xl p-5 mb-6">
          <h3 className="text-sm font-semibold mb-3">{t('batch.selectProjects')} ({selected.size})</h3>
          <div className="flex gap-3 mb-3">
            <select value={batchProvider} onChange={e => setBatchProvider(e.target.value)}
              className="px-3 py-2 bg-bg border border-border rounded-lg text-sm focus:outline-none focus:border-accent">
              {providers.map(p => (
                <option key={p.provider} value={p.provider}>
                  {PROVIDER_LABELS[p.provider] || p.provider} {p.configured ? `(${t('detail.configured')})` : `(${t('detail.notConfigured')})`}
                </option>
              ))}
            </select>
          </div>
          <button onClick={startBatch} disabled={batchLoading || selected.size === 0}
            className="px-4 py-2 bg-accent hover:bg-accent-hover disabled:opacity-50 rounded-lg text-sm font-medium transition-colors">
            {batchLoading ? t('batch.starting') : `${t('batch.start')} (${selected.size})`}
          </button>
          {batchResult && (
            <div className="mt-3 text-sm">
              <span className="text-green-500">{t('batch.started')}: {batchResult.started.length}</span>
              {batchResult.failed.length > 0 && <span className="text-severity-high ml-3">{t('batch.failed')}: {batchResult.failed.length}</span>}
            </div>
          )}
        </div>
      )}

      {/* Create form */}
      {showForm && (
        <form onSubmit={submit} className="bg-bg-card border border-border rounded-xl p-6 mb-6 space-y-4">
          {/* Source tabs */}
          <div className="flex gap-0 border-b border-border -mx-6 px-6">
            {([
              { key: 'upload' as SourceTab, icon: <Upload className="w-4 h-4" />, label: t('projects.sourceUpload') },
              { key: 'git' as SourceTab, icon: <GitBranch className="w-4 h-4" />, label: t('projects.sourceGit') },
              { key: 'local' as SourceTab, icon: <HardDrive className="w-4 h-4" />, label: t('projects.sourceLocal') },
            ]).map(tb => (
              <button key={tb.key} type="button" onClick={() => setSourceTab(tb.key)}
                className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
                  sourceTab === tb.key ? 'border-accent text-text' : 'border-transparent text-text-muted hover:text-text'
                }`}>
                {tb.icon} {tb.label}
              </button>
            ))}
          </div>

          {/* Source input per tab */}
          {sourceTab === 'upload' && (
            <div>
              <label className="block text-sm font-medium mb-1.5">{t('projects.zipFile')}</label>
              <label className="flex items-center justify-center gap-2 w-full px-3 py-6 border-2 border-dashed border-border rounded-lg text-sm cursor-pointer hover:border-accent transition-colors">
                <Upload className="w-4 h-4 text-text-muted" />
                <span className="text-text-muted">{zipFile ? zipFile.name : t('projects.zipSelect')}</span>
                <input type="file" accept=".zip" className="hidden"
                  onChange={e => setZipFile(e.target.files?.[0] || null)} />
              </label>
              <p className="text-[11px] text-text-dim mt-1.5">{t('projects.zipHint')}</p>
            </div>
          )}
          {sourceTab === 'git' && (
            <div>
              <label className="block text-sm font-medium mb-1.5">{t('projects.gitUrl')}</label>
              <input value={gitUrl} onChange={e => setGitUrl(e.target.value)}
                placeholder={t('projects.gitUrlPlaceholder')}
                className="w-full px-3 py-2 bg-bg border border-border rounded-lg text-sm font-mono focus:outline-none focus:border-accent" />
              <p className="text-[11px] text-text-dim mt-1.5">{t('projects.gitHint')}</p>
            </div>
          )}
          {sourceTab === 'local' && (
            <div>
              <label className="block text-sm font-medium mb-1.5">{t('projects.path')}</label>
              <input value={form.path} onChange={e => setForm({ ...form, path: e.target.value })}
                placeholder={t('projects.pathPlaceholder')}
                className="w-full px-3 py-2 bg-bg border border-border rounded-lg text-sm font-mono focus:outline-none focus:border-accent" required />
              <p className="text-[11px] text-text-dim mt-1.5">{t('projects.pathHint')}</p>
            </div>
          )}

          <div>
            <label className="block text-sm font-medium mb-1.5">
              {sourceTab === 'local' ? t('projects.name') : t('projects.nameOptional')}
            </label>
            <input value={form.name} onChange={e => setForm({ ...form, name: e.target.value })}
              placeholder="My Web App"
              className="w-full px-3 py-2 bg-bg border border-border rounded-lg text-sm focus:outline-none focus:border-accent"
              required={sourceTab === 'local'} />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1.5">{t('projects.desc')}</label>
            <input value={form.description} onChange={e => setForm({ ...form, description: e.target.value })}
              placeholder={t('projects.descPlaceholder')}
              className="w-full px-3 py-2 bg-bg border border-border rounded-lg text-sm focus:outline-none focus:border-accent" />
          </div>
          {/* Language selector */}
          <div>
            <label className="block text-sm font-medium mb-1.5">{t('projects.language')}</label>
            <div className="flex items-center gap-3 flex-wrap">
              <select
                value={form.language}
                onChange={e => setForm({ ...form, language: e.target.value })}
                className="px-3 py-2 bg-bg border border-border rounded-lg text-sm focus:outline-none focus:border-accent"
              >
                <option value="auto">{t('projects.languageAuto')}</option>
                <option value="PHP">PHP</option>
                <option value="Java">Java</option>
                <option value="Python">Python</option>
                <option value="Node.js">Node.js</option>
                <option value="TypeScript">TypeScript</option>
                <option value="JavaScript">JavaScript</option>
                <option value="Go">Go</option>
                <option value="C#">C#</option>
                <option value="Ruby">Ruby</option>
                <option value="Rust">Rust</option>
              </select>
              <span className="text-[11px] text-text-dim">{t('projects.languageHint')}</span>
            </div>
          </div>

          {/* Audit options (upload / git only) */}
          {sourceTab !== 'local' && (
            <div className="border border-border rounded-lg p-4 space-y-3">
              <label className="flex items-center gap-2 text-sm font-medium cursor-pointer">
                <input type="checkbox" checked={autoStart} onChange={e => setAutoStart(e.target.checked)}
                  className="w-4 h-4 accent-accent" />
                {t('projects.autoStart')}
              </label>
              {autoStart && (
                <div className="flex items-center gap-3 flex-wrap">
                  <select value={auditMode} onChange={e => setAuditMode(e.target.value)}
                    className="px-3 py-2 bg-bg border border-border rounded-lg text-sm focus:outline-none focus:border-accent">
                    <option value="quick">{t('detail.mode.quick')}</option>
                    <option value="smart">{t('detail.mode.smart')}</option>
                    <option value="comprehensive">{t('detail.mode.comprehensive')}</option>
                  </select>
                  <select value={auditProvider} onChange={e => setAuditProvider(e.target.value)}
                    className="px-3 py-2 bg-bg border border-border rounded-lg text-sm focus:outline-none focus:border-accent">
                    {providers.map(p => (
                      <option key={p.provider} value={p.provider}>
                        {PROVIDER_LABELS[p.provider] || p.provider} {p.configured ? `(${t('detail.configured')})` : `(${t('detail.notConfigured')})`}
                      </option>
                    ))}
                  </select>
                </div>
              )}
            </div>
          )}

          {error && <p className="text-severity-high text-sm">{error}</p>}
          <div className="flex items-center gap-2">
            <button type="submit" disabled={!!busy}
              className="px-4 py-2 bg-accent hover:bg-accent-hover disabled:opacity-50 rounded-lg text-sm font-medium transition-colors">
              {busy || t('projects.create')}
            </button>
            <button type="button" onClick={() => setShowForm(false)} disabled={!!busy}
              className="px-4 py-2 border border-border rounded-lg text-sm hover:bg-bg-hover transition-colors">{t('projects.cancel')}</button>
          </div>
        </form>
      )}

      {/* Status tabs */}
      <div className="flex gap-0 mb-4 border-b border-border">
        {tabs.map(tb => (
          <button key={tb.key} onClick={() => { setFilterTab(tb.key); setSelected(new Set()) }}
            className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
              filterTab === tb.key ? 'border-accent text-text' : 'border-transparent text-text-muted hover:text-text'
            }`}>
            {tb.icon}
            {tb.label}
            <span className={`ml-1 text-[10px] px-1.5 py-0.5 rounded-full ${filterTab === tb.key ? 'bg-accent/10 text-accent' : 'bg-bg-hover text-text-dim'}`}>
              {tb.count}
            </span>
          </button>
        ))}
      </div>

      {/* Project list */}
      {loading ? (
        <p className="text-text-muted text-sm py-10 text-center">{t('projects.loading')}</p>
      ) : filtered.length === 0 ? (
        <div className="text-center py-20 text-text-muted">
          <Folder className="w-12 h-12 mx-auto mb-3 opacity-40" />
          <p>{filterTab === 'all' ? t('projects.empty') :
              filterTab === 'completed' ? t('projects.noCompleted') :
              filterTab === 'in_progress' ? t('projects.noInProgress') :
              t('projects.noArchived')}
          </p>
        </div>
      ) : (
        <div className="space-y-2">
          {filtered.map(p => (
            <div key={p.id}
              onClick={() => !batchMode && navigate(`/projects/${p.id}`)}
              className={`group flex items-center gap-4 p-4 bg-bg-card border rounded-xl transition-colors ${batchMode ? 'cursor-pointer' : 'border-border hover:border-accent/50 cursor-pointer'}`}
              style={batchMode && selected.has(p.id) ? { borderColor: 'var(--color-accent)' } : {}}
            >
              {batchMode && (
                <input type="checkbox" checked={selected.has(p.id)} onChange={() => toggleSelect(p.id)} onClick={e => e.stopPropagation()}
                  className="w-4 h-4 accent-accent" />
              )}
              <div className="w-10 h-10 rounded-lg bg-accent/10 flex items-center justify-center flex-shrink-0">
                <Folder className="w-5 h-5 text-accent" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <h3 className="font-medium text-sm">{p.name}</h3>
                  {getStatusBadge(p.status || 'archived')}
                </div>
                <p className="text-text-muted text-xs font-mono truncate mt-0.5">{p.path}</p>
              </div>
              <div className="flex items-center gap-2">
                {p.tech_stack?.map(tech => (
                  <span key={tech} className="px-2 py-0.5 text-xs rounded bg-bg-hover text-text-muted flex items-center gap-1">
                    <Cpu className="w-3 h-3" />{tech}
                  </span>
                ))}
              </div>
              {!batchMode && (
                <button onClick={e => remove(p.id, e)} className="opacity-0 group-hover:opacity-100 text-text-muted hover:text-severity-high transition-all">
                  <Trash2 className="w-4 h-4" />
                </button>
              )}
              {!batchMode && <ChevronRight className="w-4 h-4 text-text-dim" />}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
