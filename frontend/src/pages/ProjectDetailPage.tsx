import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft, Play, History, Cpu, Key, Check, Trash2 } from 'lucide-react'
import { api } from '../services/api'
import type { Project, Audit, LLMProviderInfo } from '../types'
import { useI18n } from '../i18n'

const PROVIDER_LABELS: Record<string, string> = {
  deepseek: 'DeepSeek 深度求索',
  openai: 'OpenAI GPT',
  anthropic: 'Anthropic Claude',
  gemini: 'Google Gemini',
  baidu: '百度文心 ERNIE',
  doubao: '字节豆包 Doubao',
  minimax: 'MiniMax',
  zhipu: '智谱 GLM',
  qwen: '通义千问 Qwen',
  kimi: '月之暗面 Kimi',
  siliconflow: '硅基流动 SiliconFlow',
}

const PROVIDER_MODELS: Record<string, string[]> = {
  deepseek: ['deepseek-v4-flash', 'deepseek-v4-pro', 'deepseek-v4-pro[1m]'],
  openai: ['gpt-5.5', 'gpt-5.4', 'gpt-5.3-codex', 'gpt-5.2', 'o3-mini'],
  anthropic: ['claude-fable-5', 'claude-opus-4.8', 'claude-sonnet-4-20250514', 'claude-haiku-4-20250514'],
  gemini: ['gemini-3.5-flash', 'gemini-3.1-pro', 'gemini-2.5-pro', 'gemini-2.5-flash'],
  baidu: ['ernie-4.5-8k-latest', 'ernie-4.5-turbo-8k', 'ernie-speed-128k', 'ernie-x1'],
  doubao: ['doubao-seed-2.0-pro-256k-250628', 'doubao-1.5-pro-256k-250115', 'doubao-1.5-lite-32k-250115', 'doubao-seed-code'],
  minimax: ['MiniMax-M2.5', 'MiniMax-M2', 'MiniMax-Text-01'],
  zhipu: ['glm-5.2', 'glm-5.1', 'glm-5', 'glm-4-flash'],
  qwen: ['qwen3.8-max-preview', 'qwen3.7-plus', 'qwen3.7-max-preview', 'qwen-coder-plus'],
  kimi: ['kimi-k3', 'moonshot-v1-128k', 'kimi-latest'],
  siliconflow: ['Qwen/Qwen3.8-Max-Preview', 'deepseek-ai/DeepSeek-V4-Flash', 'Qwen/Qwen3-Coder-480B'],
}

export default function ProjectDetailPage() {
  const { t } = useI18n()
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [project, setProject] = useState<Project | null>(null)
  const [audits, setAudits] = useState<Audit[]>([])
  const [providers, setProviders] = useState<LLMProviderInfo[]>([])
  const [savedKeys, setSavedKeys] = useState<Set<string>>(new Set())
  const [loading, setLoading] = useState(true)
  const [starting, setStarting] = useState(false)

  const [mode, setMode] = useState('smart')
  const [provider, setProvider] = useState('deepseek')
  const [apiKey, setApiKey] = useState('')
  const [model, setModel] = useState('')
  const [showAdvanced, setShowAdvanced] = useState(false)

  const load = async () => {
    if (!id) return
    try {
      const [proj, au, pv, keys] = await Promise.all([
        api.getProject(id),
        api.getProjectAudits(id),
        api.getLLMProviders(),
        api.listAPIKeys().catch(() => []),
      ])
      setProject(proj)
      setAudits(au)
      setProviders(pv)
      setSavedKeys(new Set(keys.map(k => k.provider)))
      // Prefer provider that has a saved key (DB), then .env-configured, else first
      const preferred = keys[0]?.provider || pv.find(p => p.configured)?.provider
      if (preferred) {
        setProvider(preferred)
        const p = pv.find(x => x.provider === preferred)
        if (p) setModel(p.default_model)
      }
    } catch (e) {
      // ignore
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [id])

  const selectedProviderInfo = providers.find(p => p.provider === provider)
  const isConfigured = selectedProviderInfo?.configured ?? false
  const hasSavedKey = savedKeys.has(provider)

  const startAudit = async () => {
    if (!id) return
    if (!isConfigured && !hasSavedKey && !apiKey.trim()) {
      alert(t('detail.enterKeyPrompt'))
      return
    }
    setStarting(true)
    try {
      const result = await api.createAudit({
        project_id: id,
        mode,
        llm_provider: provider,
        llm_model: model || undefined,
        llm_api_key: apiKey || undefined,
      })
      navigate(`/audits/${result.audit_id}`)
    } catch (e: any) {
      alert(e.message)
    } finally {
      setStarting(false)
    }
  }

  const deleteAudit = async (a: Audit, e: React.MouseEvent) => {
    e.stopPropagation()
    if (!confirm(t('audit.deleteConfirm'))) return
    try {
      const r = await api.deleteAudit(a.id)
      alert(t('audit.deleted').replace('{n}', String(r.deleted_audits)).replace('{f}', String(r.deleted_findings)).replace('{l}', String(r.deleted_logs)))
      load()
    } catch (err: any) {
      alert(err.message || t('audit.deleteRunning'))
    }
  }

  const statusLabel = (s: string) => t(`audit.status.${s}`) || s
  const modeLabel = (m: string) => t(`audit.mode.${m}`) || m

  if (loading) return <div className="p-8 text-text-muted">{t('common.loading')}</div>
  if (!project) return <div className="p-8 text-text-muted">{t('projects.title')} {t('common.notFound')}</div>

  const statusColor = (s: string) => ({
    running: 'text-accent',
    completed: 'text-green-500',
    failed: 'text-severity-high',
    pending: 'text-text-muted',
    aborted: 'text-severity-medium',
    max_turns: 'text-severity-medium',
  }[s] || 'text-text-muted')

  return (
    <div className="p-8 max-w-5xl">
      <button onClick={() => navigate('/')} className="flex items-center gap-1 text-text-muted hover:text-text text-sm mb-4">
        <ArrowLeft className="w-4 h-4" /> {t('detail.back')}
      </button>

      {/* Project Info */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold">{project.name}</h1>
        <p className="text-text-muted text-sm font-mono mt-1">{project.path}</p>
        <div className="flex gap-2 mt-3">
          {project.tech_stack?.map(tech => (
            <span key={tech} className="px-2 py-1 text-xs rounded-md bg-bg-hover text-text-muted flex items-center gap-1">
              <Cpu className="w-3 h-3" />{tech}
            </span>
          ))}
        </div>
        {project.description && <p className="text-text-muted text-sm mt-3">{project.description}</p>}
      </div>

      {/* Start Audit */}
      <div className="bg-bg-card border border-border rounded-xl p-5 mb-6">
        <h2 className="text-sm font-semibold mb-4 flex items-center gap-2">
          <Play className="w-4 h-4 text-accent" /> {t('detail.startAudit')}
        </h2>

        {/* Mode + Provider */}
        <div className="flex gap-3 mb-4">
          <div className="flex-1">
            <label className="block text-xs text-text-muted mb-1.5">{t('detail.auditMode')}</label>
            <select value={mode} onChange={e => setMode(e.target.value)}
              className="w-full px-3 py-2 bg-bg border border-border rounded-lg text-sm focus:outline-none focus:border-accent">
              <option value="quick">{t('detail.mode.quick')}</option>
              <option value="smart">{t('detail.mode.smart')}</option>
              <option value="comprehensive">{t('detail.mode.comprehensive')}</option>
            </select>
          </div>
          <div className="flex-1">
            <label className="block text-xs text-text-muted mb-1.5">{t('detail.llmProvider')}</label>
            <select value={provider} onChange={e => {
              setProvider(e.target.value)
              const p = providers.find(p => p.provider === e.target.value)
              setModel(p?.default_model || '')
              setApiKey('')
            }}
              className="w-full px-3 py-2 bg-bg border border-border rounded-lg text-sm focus:outline-none focus:border-accent">
              {providers.map(p => (
                <option key={p.provider} value={p.provider}>
                  {PROVIDER_LABELS[p.provider] || p.provider}
                  {p.configured
                    ? ` ✓ .env`
                    : savedKeys.has(p.provider)
                      ? ` ✓ key`
                      : ` ·`}
                </option>
              ))}
            </select>
          </div>
          <div className="flex-1">
            <label className="block text-xs text-text-muted mb-1.5">{t('detail.model')}</label>
            <select value={model} onChange={e => setModel(e.target.value)}
              className="w-full px-3 py-2 bg-bg border border-border rounded-lg text-sm focus:outline-none focus:border-accent">
              {(PROVIDER_MODELS[provider] || []).map(m => (
                <option key={m} value={m}>{m}</option>
              ))}
            </select>
          </div>
        </div>

        {/* API Key — only show if not configured in .env and not saved in DB */}
        {!isConfigured && !hasSavedKey && (
          <div className="mb-4">
            <label className="block text-xs text-text-muted mb-1.5 flex items-center gap-1">
              <Key className="w-3 h-3" />
              {PROVIDER_LABELS[provider]} {t('detail.apiKey')}
              <span className="text-severity-high">*</span>
              <span className="text-text-dim">{t('detail.apiKeyRequired')}</span>
            </label>
            <input
              type="password"
              value={apiKey}
              onChange={e => setApiKey(e.target.value)}
              placeholder={t('detail.apiKeyPlaceholder')}
              className="w-full px-3 py-2 bg-bg border border-border rounded-lg text-sm font-mono focus:outline-none focus:border-accent"
            />
          </div>
        )}

        {isConfigured && (
          <div className="mb-4 flex items-center gap-1.5 text-xs text-green-500">
            <Check className="w-3 h-3" />
            {t('detail.apiKeyConfigured')}
          </div>
        )}

        {/* Advanced toggle */}
        <button
          onClick={() => setShowAdvanced(!showAdvanced)}
          className="text-xs text-text-muted hover:text-text mb-3"
        >
          {showAdvanced ? '▾' : '▸'} {t('detail.advanced')}
        </button>

        {showAdvanced && (
          <div className="mb-4 p-3 bg-bg rounded-lg border border-border space-y-3">
            <div>
              <label className="block text-xs text-text-muted mb-1.5">{t('detail.maxTurns')}</label>
              <input type="number" defaultValue={50} min={5} max={200}
                className="w-32 px-3 py-2 bg-bg border border-border rounded-lg text-sm focus:outline-none focus:border-accent"
              />
            </div>
          </div>
        )}

        <button onClick={startAudit} disabled={starting || !hasSavedKey}
          className="px-4 py-2 bg-accent hover:bg-accent-hover disabled:opacity-50 disabled:cursor-not-allowed rounded-lg text-sm font-medium transition-colors">
          {starting ? t('detail.starting') : t('detail.start')}
        </button>
      </div>

      {/* Audit History */}
      <div>
        <h2 className="text-sm font-semibold mb-3 flex items-center gap-2">
          <History className="w-4 h-4" /> {t('detail.auditHistory')}
        </h2>
        {audits.length === 0 ? (
          <p className="text-text-muted text-sm">{t('detail.noAudits')}</p>
        ) : (
          <div className="space-y-2">
            {audits.map(a => (
              <div key={a.id} onClick={() => navigate(`/audits/${a.id}`)}
                className="group flex items-center gap-4 p-3 bg-bg-card border border-border rounded-lg hover:border-accent/50 cursor-pointer transition-colors">
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className={`text-xs font-medium ${statusColor(a.status)}`}>● {a.status}</span>
                    <span className="text-text-muted text-xs">{a.mode}</span>
                    <span className="text-text-muted text-xs">· {a.llm_provider}</span>
                  </div>
                  <div className="text-text-muted text-xs mt-0.5">
                    {a.turns_completed} {t('audit.turns')} · {a.total_tool_calls} {t('audit.toolCalls')} · {(a.total_tokens / 1000).toFixed(1)}K {t('audit.tokens')}
                  </div>
                </div>
                {a.error_message && <span className="text-severity-high text-xs truncate max-w-48">{a.error_message}</span>}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
