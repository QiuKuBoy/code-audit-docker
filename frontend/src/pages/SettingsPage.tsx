import { useState, useEffect } from 'react'
import { Plus, Trash2, TestTube, Save, X, Check, AlertCircle, Loader2, Edit3 } from 'lucide-react'
import { api } from '../services/api'
import type { APIKey, APIKeyCreateParams, APIKeyTestResult } from '../types'
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

interface DraftKey {
  provider: string
  api_key: string
  base_url: string
  model: string
  label: string
}

const EMPTY_DRAFT = (provider = 'deepseek'): DraftKey => ({
  provider,
  api_key: '',
  base_url: '',
  model: '',
  label: '',
})

export default function SettingsPage() {
  const { t } = useI18n()
  const [keys, setKeys] = useState<APIKey[]>([])
  const [loading, setLoading] = useState(true)
  const [creating, setCreating] = useState(false)
  const [draft, setDraft] = useState<DraftKey>(EMPTY_DRAFT())
  const [testResult, setTestResult] = useState<APIKeyTestResult | null>(null)
  const [testing, setTesting] = useState(false)
  const [saving, setSaving] = useState(false)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editDraft, setEditDraft] = useState<DraftKey>(EMPTY_DRAFT())
  const [testingId, setTestingId] = useState<string | null>(null)
  const [revealIds, setRevealIds] = useState<Set<string>>(new Set())

  const load = async () => {
    try {
      const data = await api.listAPIKeys()
      setKeys(data)
    } catch (e) {
      // ignore
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const handleTestDraft = async () => {
    if (!draft.api_key.trim()) {
      alert(t('settings.apiKey') + ' is required')
      return
    }
    setTesting(true)
    setTestResult(null)
    try {
      const res = await api.testAPIKeyWithoutSaving({
        provider: draft.provider,
        api_key: draft.api_key,
        base_url: draft.base_url || undefined,
        model: draft.model || undefined,
        label: draft.label || undefined,
      })
      setTestResult(res)
    } catch (e: any) {
      setTestResult({
        provider: draft.provider,
        ok: false,
        status: 'failed',
        model: draft.model,
        message: e.message,
        latency_ms: 0,
      })
    } finally {
      setTesting(false)
    }
  }

  const handleSaveDraft = async () => {
    if (!draft.api_key.trim()) {
      alert(t('settings.apiKey') + ' is required')
      return
    }
    setSaving(true)
    try {
      await api.createAPIKey({
        provider: draft.provider,
        api_key: draft.api_key,
        base_url: draft.base_url || undefined,
        model: draft.model || undefined,
        label: draft.label || undefined,
      })
      setCreating(false)
      setDraft(EMPTY_DRAFT())
      setTestResult(null)
      await load()
    } catch (e: any) {
      alert(e.message)
    } finally {
      setSaving(false)
    }
  }

  const handleTestStored = async (id: string) => {
    setTestingId(id)
    try {
      await api.testAPIKey(id)
      await load()
    } catch (e: any) {
      alert(e.message)
    } finally {
      setTestingId(null)
    }
  }

  const handleDelete = async (k: APIKey) => {
    if (!confirm(t('settings.deleteConfirm'))) return
    try {
      await api.deleteAPIKey(k.id)
      await load()
    } catch (e: any) {
      alert(e.message)
    }
  }

  const startEdit = (k: APIKey) => {
    setEditingId(k.id)
    setEditDraft({
      provider: k.provider,
      api_key: k.api_key,
      base_url: k.base_url,
      model: k.model,
      label: k.label,
    })
  }

  const saveEdit = async () => {
    if (!editingId) return
    try {
      await api.updateAPIKey(editingId, {
        api_key: editDraft.api_key,
        base_url: editDraft.base_url,
        model: editDraft.model,
        label: editDraft.label,
      })
      setEditingId(null)
      await load()
    } catch (e: any) {
      alert(e.message)
    }
  }

  const toggleReveal = (id: string) => {
    setRevealIds(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const masked = (s: string) => {
    if (!s) return ''
    if (s.length <= 8) return '••••••••'
    return s.slice(0, 4) + '••••••••' + s.slice(-4)
  }

  const statusBadge = (k: APIKey) => {
    if (k.last_status === 'ok') {
      return <span className="text-xs px-2 py-0.5 rounded bg-green-500/10 text-green-500">{t('settings.testOk')}</span>
    }
    if (k.last_status === 'failed') {
      return <span className="text-xs px-2 py-0.5 rounded bg-severity-high/10 text-severity-high">{t('settings.testFailed')}</span>
    }
    return <span className="text-xs px-2 py-0.5 rounded bg-text-muted/10 text-text-muted">{t('settings.neverTested')}</span>
  }

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">{t('settings.title')}</h1>
          <p className="text-text-muted text-sm mt-1">{t('settings.subtitle')}</p>
        </div>
        {!creating && (
          <button
            onClick={() => { setCreating(true); setTestResult(null); setDraft(EMPTY_DRAFT()) }}
            className="flex items-center gap-2 px-4 py-2 bg-accent text-white rounded-lg hover:bg-accent/90 transition-colors"
          >
            <Plus className="w-4 h-4" />
            {t('settings.new')}
          </button>
        )}
      </div>

      {/* Create form */}
      {creating && (
        <div className="mb-6 bg-bg-card border border-border rounded-lg p-5">
          <h2 className="font-semibold mb-4 flex items-center gap-2">
            <Plus className="w-4 h-4" />
            {t('settings.createKey')}
          </h2>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs text-text-muted mb-1">{t('settings.provider')}</label>
              <select
                value={draft.provider}
                onChange={e => setDraft({ ...draft, provider: e.target.value, model: '' })}
                className="w-full bg-bg border border-border rounded px-3 py-2 text-sm"
              >
                {Object.keys(PROVIDER_LABELS).map(p => (
                  <option key={p} value={p}>{PROVIDER_LABELS[p]}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs text-text-muted mb-1">{t('settings.label')}</label>
              <input
                type="text"
                value={draft.label}
                onChange={e => setDraft({ ...draft, label: e.target.value })}
                placeholder="Personal / Work / Test..."
                className="w-full bg-bg border border-border rounded px-3 py-2 text-sm"
              />
            </div>
            <div className="col-span-2">
              <label className="block text-xs text-text-muted mb-1">{t('settings.apiKey')} *</label>
              <input
                type="password"
                value={draft.api_key}
                onChange={e => setDraft({ ...draft, api_key: e.target.value })}
                placeholder={t('detail.apiKeyPlaceholder')}
                className="w-full bg-bg border border-border rounded px-3 py-2 text-sm font-mono"
              />
            </div>
            <div>
              <label className="block text-xs text-text-muted mb-1">{t('settings.baseUrl')}</label>
              <input
                type="text"
                value={draft.base_url}
                onChange={e => setDraft({ ...draft, base_url: e.target.value })}
                placeholder="https://api.example.com/v1"
                className="w-full bg-bg border border-border rounded px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label className="block text-xs text-text-muted mb-1">{t('settings.model')}</label>
              <select
                value={draft.model}
                onChange={e => setDraft({ ...draft, model: e.target.value })}
                className="w-full bg-bg border border-border rounded px-3 py-2 text-sm"
              >
                <option value="">（使用默认）</option>
                {(PROVIDER_MODELS[draft.provider] || []).map(m => (
                  <option key={m} value={m}>{m}</option>
                ))}
              </select>
            </div>
          </div>

          {/* Test result */}
          {testResult && (
            <div className={`mt-4 p-3 rounded text-sm flex items-start gap-2 ${testResult.ok ? 'bg-green-500/10 text-green-500' : 'bg-severity-high/10 text-severity-high'}`}>
              {testResult.ok ? <Check className="w-4 h-4 mt-0.5 flex-shrink-0" /> : <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />}
              <div className="flex-1 min-w-0">
                <div className="font-medium">{testResult.ok ? t('settings.testOk') : t('settings.testFailed')} - {testResult.latency_ms}ms</div>
                <div className="text-xs mt-1 break-all opacity-80">{testResult.message}</div>
                {testResult.model && <div className="text-xs mt-1 opacity-60">Model: {testResult.model}</div>}
              </div>
            </div>
          )}

          <div className="mt-5 flex items-center gap-2">
            <button
              onClick={handleTestDraft}
              disabled={testing || !draft.api_key.trim()}
              className="flex items-center gap-2 px-4 py-2 bg-bg-hover border border-border rounded hover:bg-border transition-colors disabled:opacity-50"
            >
              {testing ? <Loader2 className="w-4 h-4 animate-spin" /> : <TestTube className="w-4 h-4" />}
              {testing ? t('settings.testing') : t('settings.test')}
            </button>
            <button
              onClick={handleSaveDraft}
              disabled={saving || !draft.api_key.trim()}
              className="flex items-center gap-2 px-4 py-2 bg-accent text-white rounded hover:bg-accent/90 transition-colors disabled:opacity-50"
            >
              {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
              {saving ? t('common.loading') : t('settings.save')}
            </button>
            <button
              onClick={() => { setCreating(false); setTestResult(null); setDraft(EMPTY_DRAFT()) }}
              className="flex items-center gap-2 px-4 py-2 text-text-muted hover:text-text transition-colors"
            >
              <X className="w-4 h-4" />
              {t('settings.cancel')}
            </button>
            <span className="text-xs text-text-muted ml-auto">{t('settings.testingThenSave')}</span>
          </div>
        </div>
      )}

      {/* Key list */}
      {loading ? (
        <div className="text-text-muted text-center py-12">{t('common.loading')}</div>
      ) : keys.length === 0 ? (
        <div className="text-center py-16 bg-bg-card border border-border rounded-lg">
          <p className="text-text-muted">{t('settings.empty')}</p>
        </div>
      ) : (
        <div className="space-y-3">
          {keys.map(k => (
            <div key={k.id} className="bg-bg-card border border-border rounded-lg p-5">
              <div className="flex items-start justify-between">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-2">
                    <h3 className="font-semibold">{PROVIDER_LABELS[k.provider] || k.provider}</h3>
                    {k.label && <span className="text-xs px-2 py-0.5 rounded bg-bg-hover text-text-muted">{k.label}</span>}
                    {statusBadge(k)}
                  </div>

                  {editingId === k.id ? (
                    <div className="grid grid-cols-2 gap-3 mt-3">
                      <div className="col-span-2">
                        <label className="block text-xs text-text-muted mb-1">{t('settings.apiKey')}</label>
                        <input type="password" value={editDraft.api_key} onChange={e => setEditDraft({ ...editDraft, api_key: e.target.value })}
                          className="w-full bg-bg border border-border rounded px-3 py-2 text-sm font-mono" />
                      </div>
                      <div>
                        <label className="block text-xs text-text-muted mb-1">{t('settings.baseUrl')}</label>
                        <input type="text" value={editDraft.base_url} onChange={e => setEditDraft({ ...editDraft, base_url: e.target.value })}
                          className="w-full bg-bg border border-border rounded px-3 py-2 text-sm" />
                      </div>
                      <div>
                        <label className="block text-xs text-text-muted mb-1">{t('settings.model')}</label>
                        <select value={editDraft.model} onChange={e => setEditDraft({ ...editDraft, model: e.target.value })}
                          className="w-full bg-bg border border-border rounded px-3 py-2 text-sm">
                          <option value="">（使用默认）</option>
                          {(PROVIDER_MODELS[k.provider] || []).map(m => <option key={m} value={m}>{m}</option>)}
                        </select>
                      </div>
                      <div className="col-span-2">
                        <label className="block text-xs text-text-muted mb-1">{t('settings.label')}</label>
                        <input type="text" value={editDraft.label} onChange={e => setEditDraft({ ...editDraft, label: e.target.value })}
                          className="w-full bg-bg border border-border rounded px-3 py-2 text-sm" />
                      </div>
                      <div className="col-span-2 flex items-center gap-2 mt-1">
                        <button onClick={saveEdit} className="flex items-center gap-2 px-3 py-1.5 bg-accent text-white rounded text-sm">
                          <Save className="w-3.5 h-3.5" />{t('settings.save')}
                        </button>
                        <button onClick={() => setEditingId(null)} className="flex items-center gap-2 px-3 py-1.5 text-text-muted text-sm">
                          <X className="w-3.5 h-3.5" />{t('settings.cancel')}
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div className="space-y-1.5 text-sm">
                      <div className="flex items-center gap-2">
                        <span className="text-text-muted text-xs w-20">{t('settings.apiKey')}:</span>
                        <code className="font-mono text-xs">{revealIds.has(k.id) ? k.api_key : masked(k.api_key)}</code>
                        <button onClick={() => toggleReveal(k.id)} className="text-xs text-accent hover:underline">
                          {revealIds.has(k.id) ? 'Hide' : 'Show'}
                        </button>
                      </div>
                      {k.model && (
                        <div className="flex items-center gap-2">
                          <span className="text-text-muted text-xs w-20">{t('settings.model')}:</span>
                          <span className="font-mono text-xs">{k.model}</span>
                        </div>
                      )}
                      {k.base_url && (
                        <div className="flex items-center gap-2">
                          <span className="text-text-muted text-xs w-20">Base URL:</span>
                          <span className="font-mono text-xs truncate">{k.base_url}</span>
                        </div>
                      )}
                      <div className="flex items-center gap-2">
                        <span className="text-text-muted text-xs w-20">{t('settings.lastTest')}:</span>
                        <span className="text-xs">
                          {k.last_tested_at ? new Date(k.last_tested_at).toLocaleString() : t('settings.neverTested')}
                        </span>
                      </div>
                      {k.last_error && (
                        <div className="flex items-start gap-2">
                          <span className="text-text-muted text-xs w-20 flex-shrink-0">Error:</span>
                          <span className="text-xs text-severity-high break-all">{k.last_error}</span>
                        </div>
                      )}
                    </div>
                  )}
                </div>

                {editingId !== k.id && (
                  <div className="flex items-center gap-1 ml-3">
                    <button
                      onClick={() => handleTestStored(k.id)}
                      disabled={testingId === k.id}
                      className="p-2 text-text-muted hover:text-accent hover:bg-bg-hover rounded transition-colors disabled:opacity-50"
                      title={t('settings.test')}
                    >
                      {testingId === k.id ? <Loader2 className="w-4 h-4 animate-spin" /> : <TestTube className="w-4 h-4" />}
                    </button>
                    <button
                      onClick={() => startEdit(k)}
                      className="p-2 text-text-muted hover:text-accent hover:bg-bg-hover rounded transition-colors"
                      title="Edit"
                    >
                      <Edit3 className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => handleDelete(k)}
                      className="p-2 text-text-muted hover:text-severity-high hover:bg-bg-hover rounded transition-colors"
                      title={t('settings.delete')}
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}