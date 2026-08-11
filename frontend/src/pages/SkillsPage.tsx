
import { useState, useEffect, useRef } from 'react'
import { BookOpen, CheckCircle2, XCircle, Zap, Search, Cpu, ChevronRight, X, Plus, Trash2, Upload } from 'lucide-react'
import { api } from '../services/api'
import type { SkillInfo } from '../types'
import { useI18n } from '../i18n'

const EFFICIENCY_COLORS: Record<string, string> = {
  high: 'text-severity-high',
  medium: 'text-severity-medium',
  low: 'text-severity-low',
}

function effTier(e: number): string {
  if (e >= 85) return 'high'
  if (e >= 60) return 'medium'
  return 'low'
}

function effLabel(e: number, t: (k: string) => string): string {
  if (e >= 85) return 'S'
  if (e >= 70) return 'A'
  if (e >= 55) return 'B'
  return 'C'
}

export default function SkillsPage() {
  const { t } = useI18n()
  const [skills, setSkills] = useState<SkillInfo[]>([])
  const [loading, setLoading] = useState(true)
  const [query, setQuery] = useState('')
  const [detail, setDetail] = useState<SkillInfo | null>(null)
  const [detailContent, setDetailContent] = useState('')
  const [detailLoading, setDetailLoading] = useState(false)
  const [showCreate, setShowCreate] = useState(false)
  const [createForm, setCreateForm] = useState({ name: '', display_name: '', content: '' })
  const [createError, setCreateError] = useState('')
  const [creating, setCreating] = useState(false)
  const [uploading, setUploading] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const load = async () => {
    try {
      const res = await api.listSkills()
      setSkills(res.skills || [])
    } catch (_) {} finally { setLoading(false) }
  }

  useEffect(() => { load() }, [])

  const openDetail = async (s: SkillInfo) => {
    setDetail(s)
    setDetailLoading(true)
    setDetailContent('')
    try {
      const res = await api.getSkillDetail(s.name)
      setDetailContent(res.content || '')
    } catch (_) {} finally { setDetailLoading(false) }
  }

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    setCreateError('')
    setCreating(true)
    try {
      await api.createSkill(createForm)
      setShowCreate(false)
      setCreateForm({ name: '', display_name: '', content: '' })
      await load()
      alert(t('skills.createSuccess'))
    } catch (err: any) { alert(err.message || 'Failed') }
    finally { setCreating(false) }
  }

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setUploading(true)
    try {
      await api.uploadSkill(file)
      await load()
      alert(t('skills.uploadSuccess'))
    } catch (err: any) { alert(err.message || t('skills.uploadFailed')) }
    finally {
      setUploading(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  const handleDelete = async (s: SkillInfo) => {
    if (!confirm(t('skills.deleteConfirm').replace('{name}', s.display_name))) return
    try {
      await api.deleteSkill(s.name)
      if (detail?.name === s.name) setDetail(null)
      await load()
      alert(t('skills.deleteSuccess'))
    } catch (err: any) { alert(err.message || 'Failed') }
  }

  const filtered = skills.filter(s =>
    !query || s.name.toLowerCase().includes(query.toLowerCase()) || s.display_name.includes(query)
  )

  return (
    <div className="p-8 max-w-6xl">
      <div className="flex items-center justify-between mb-2 flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <BookOpen className="w-6 h-6 text-accent" /> Skill
          </h1>
          <p className="text-text-muted text-sm mt-1">{t('skills.subtitle')}</p>
        </div>
        <div className="flex items-center gap-2">
          <input
            ref={fileInputRef}
            type="file"
            accept=".md,.zip"
            onChange={handleUpload}
            className="hidden"
          />
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading}
            className="flex items-center gap-1.5 px-3 py-2 border border-border hover:bg-bg-hover rounded-lg text-sm transition-colors disabled:opacity-50"
          >
            <Upload className="w-4 h-4" /> {uploading ? t('common.loading') : t('skills.upload')}
          </button>
          <button
            onClick={() => setShowCreate(true)}
            className="flex items-center gap-1.5 px-3 py-2 bg-accent hover:bg-accent-hover rounded-lg text-sm font-medium transition-colors"
          >
            <Plus className="w-4 h-4" /> {t('skills.new')}
          </button>
          <div className="relative">
            <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-text-dim" />
            <input
              value={query}
              onChange={e => setQuery(e.target.value)}
              placeholder={t('skills.search')}
              className="pl-9 pr-3 py-2 bg-bg-card border border-border rounded-lg text-sm focus:outline-none focus:border-accent w-56"
            />
          </div>
        </div>
      </div>

      {/* Efficiency legend */}
      <div className="flex items-center gap-4 mb-5 text-xs text-text-muted">
        <span className="flex items-center gap-1.5">
          <Zap className="w-3.5 h-3.5 text-severity-high" />
          {t('skills.sortedByEfficiency')}
        </span>
        {['S', 'A', 'B', 'C'].map((l, i) => (
          <span key={l} className="flex items-center gap-1">
            <span className={`w-4 h-4 rounded flex items-center justify-center text-[9px] font-bold ${
              i === 0 ? 'bg-severity-high/15 text-severity-high' :
              i === 1 ? 'bg-severity-medium/15 text-severity-medium' :
              i === 2 ? 'bg-severity-low/15 text-severity-low' :
              'bg-bg-hover text-text-dim'
            }`}>{l}</span>
            {i === 0 ? t('skills.tierS') : i === 1 ? t('skills.tierA') : i === 2 ? t('skills.tierB') : t('skills.tierC')}
          </span>
        ))}
      </div>

      {loading ? (
        <p className="text-text-muted text-sm py-10 text-center">{t('common.loading')}</p>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {filtered.map(s => {
            const tier = effTier(s.efficiency)
            return (
              <div key={s.name} className="group bg-bg-card border border-border rounded-xl p-4 hover:border-accent/40 transition-colors">
                <div className="flex items-start justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <span className={`w-7 h-7 rounded-lg flex items-center justify-center text-xs font-bold ${
                      tier === 'high' ? 'bg-severity-high/15 text-severity-high' :
                      tier === 'medium' ? 'bg-severity-medium/15 text-severity-medium' :
                      'bg-bg-hover text-text-muted'
                    }`}>
                      {effLabel(s.efficiency, t)}
                    </span>
                    <div>
                      <div className="font-semibold text-sm">{s.display_name}</div>
                      <div className="text-[10px] font-mono text-text-dim">{s.name}</div>
                    </div>
                  </div>
                  <span className="text-xs text-text-muted flex items-center gap-1">
                    <Zap className={`w-3.5 h-3.5 ${EFFICIENCY_COLORS[tier]}`} />
                    {s.efficiency}
                  </span>
                </div>

                <p className="text-xs text-text-muted mb-3 line-clamp-2 h-8">{s.value_desc || s.overview}</p>

                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    {s.has_checklist && (
                      <span className="flex items-center gap-1 text-[10px] text-text-muted">
                        <Cpu className="w-3 h-3" />
                        {s.checklist_langs.slice(0, 3).join(' / ')}
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => openDetail(s)}
                      className="flex items-center gap-1 text-xs text-accent hover:underline"
                    >
                      {t('skills.view')} <ChevronRight className="w-3 h-3" />
                    </button>
                    <button
                      onClick={() => handleDelete(s)}
                      className="text-text-dim hover:text-severity-high transition-colors opacity-0 group-hover:opacity-100"
                      title={t('skills.deleteConfirm').replace('{name}', s.display_name)}
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                    <span className={`flex items-center gap-1 text-[10px] ${s.enabled ? 'text-green-500' : 'text-text-dim'}`}>
                      {s.enabled ? <CheckCircle2 className="w-3 h-3" /> : <XCircle className="w-3 h-3" />}
                      {s.enabled ? t('skills.enabled') : t('skills.disabled')}
                    </span>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* Create modal */}
      {showCreate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/50" onClick={() => setShowCreate(false)} />
          <form onSubmit={handleCreate} className="relative w-[560px] max-w-[92vw] bg-bg-card border border-border rounded-xl p-6 space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold flex items-center gap-2">
                <Plus className="w-5 h-5 text-accent" /> {t('skills.newTitle')}
              </h2>
              <button type="button" onClick={() => setShowCreate(false)} className="text-text-muted hover:text-text">
                <X className="w-4 h-4" />
              </button>
            </div>
            <div>
              <label className="block text-sm font-medium mb-1.5">{t('skills.name')}</label>
              <input
                value={createForm.name}
                onChange={e => setCreateForm({ ...createForm, name: e.target.value })}
                placeholder={t('skills.namePlaceholder')}
                className="w-full px-3 py-2 bg-bg border border-border rounded-lg text-sm font-mono focus:outline-none focus:border-accent"
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1.5">{t('projects.name')}</label>
              <input
                value={createForm.display_name}
                onChange={e => setCreateForm({ ...createForm, display_name: e.target.value })}
                placeholder="JWT 审计"
                className="w-full px-3 py-2 bg-bg border border-border rounded-lg text-sm focus:outline-none focus:border-accent"
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1.5">{t('skills.content')}</label>
              <textarea
                value={createForm.content}
                onChange={e => setCreateForm({ ...createForm, content: e.target.value })}
                placeholder={t('skills.contentPlaceholder')}
                rows={10}
                className="w-full px-3 py-2 bg-bg border border-border rounded-lg text-sm font-mono focus:outline-none focus:border-accent resize-y"
                required
              />
            </div>
            {createError && <p className="text-severity-high text-sm">{createError}</p>}
            <div className="flex gap-2 justify-end">
              <button type="button" onClick={() => setShowCreate(false)}
                className="px-4 py-2 border border-border rounded-lg text-sm hover:bg-bg-hover transition-colors">
                {t('projects.cancel')}
              </button>
              <button type="submit" disabled={creating}
                className="px-4 py-2 bg-accent hover:bg-accent-hover rounded-lg text-sm font-medium disabled:opacity-50 transition-colors">
                {creating ? t('common.loading') : t('skills.create')}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Detail drawer */}
      {detail && (
        <div className="fixed inset-0 z-50 flex">
          <div className="flex-1 bg-black/50" onClick={() => setDetail(null)} />
          <div className="w-[520px] max-w-full bg-bg-card border-l border-border flex flex-col">
            <div className="flex items-center justify-between px-5 py-4 border-b border-border">
              <div className="flex items-center gap-2">
                <span className="w-7 h-7 rounded-lg bg-accent/15 text-accent flex items-center justify-center text-xs font-bold">
                  {effLabel(detail.efficiency, t)}
                </span>
                <div>
                  <div className="font-semibold">{detail.display_name}</div>
                  <div className="text-[10px] font-mono text-text-dim">{detail.name}</div>
                </div>
              </div>
              <button onClick={() => setDetail(null)} className="text-text-muted hover:text-text">
                <X className="w-4 h-4" />
              </button>
            </div>
            <div className="flex-1 overflow-y-auto p-5">
              {detailLoading ? (
                <p className="text-text-muted text-sm">{t('common.loading')}</p>
              ) : (
                <pre className="text-xs text-text-muted whitespace-pre-wrap font-mono leading-relaxed">
                  {detailContent}
                </pre>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
