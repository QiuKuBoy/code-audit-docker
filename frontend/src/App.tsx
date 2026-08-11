
import { Routes, Route, Link, useLocation } from 'react-router-dom'
import {
  Shield, FolderPlus, List, Activity, Languages, LayoutDashboard, KeyRound,
  Folder, FolderOpen, ChevronRight, ChevronDown, Server, Globe, Plus,
  CheckCircle2, RotateCcw, Circle, Trash2, BookOpen, Plug,
} from 'lucide-react'
import { useState, useEffect, createContext, useContext, useCallback, type ReactNode } from 'react'
import ProjectsPage from './pages/ProjectsPage'
import ProjectDetailPage from './pages/ProjectDetailPage'
import AuditDetailPage from './pages/AuditDetailPage'
import DashboardPage from './pages/DashboardPage'
import SettingsPage from './pages/SettingsPage'
import SkillsPage from './pages/SkillsPage'
import MCPServersPage from './pages/MCPServersPage'
import { I18nProvider, useI18n } from './i18n'
import { api } from './services/api'
import type { Project, Audit } from './types'

/* ── Theme Context ────────────────────────────────────────── */
type Theme = 'dark' | 'light'
const ThemeCtx = createContext<{ theme: Theme; toggle: () => void } | null>(null)

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<Theme>(() => {
    const saved = localStorage.getItem('code-audit-theme')
    return (saved === 'light' || saved === 'dark') ? saved : 'dark'
  })
  useEffect(() => {
    document.documentElement.classList.toggle('light', theme === 'light')
    localStorage.setItem('code-audit-theme', theme)
  }, [theme])
  const toggle = () => setTheme(t => t === 'dark' ? 'light' : 'dark')
  return <ThemeCtx.Provider value={{ theme, toggle }}>{children}</ThemeCtx.Provider>
}

export function useTheme() {
  const ctx = useContext(ThemeCtx)
  if (!ctx) throw new Error('useTheme must be used within ThemeProvider')
  return ctx
}

export default function App() {
  return (
    <ThemeProvider>
      <I18nProvider>
        <AppInner />
      </I18nProvider>
    </ThemeProvider>
  )
}

/* ── Project status helper ────────────────────────────────── */
type ProjectStatus = 'completed' | 'in_progress' | 'unaudited'

function projectStatus(audits: Audit[] | undefined): ProjectStatus {
  if (!audits || audits.length === 0) return 'unaudited'
  const latest = audits[0]
  if (latest.status === 'running' || latest.status === 'pending') return 'in_progress'
  if (latest.status === 'completed') return 'completed'
  return 'unaudited'
}

interface ProjectWithStatus extends Project { status: ProjectStatus }

/* ── Sidebar project section ──────────────────────────────── */
function ProjectSection({ activeProjectPath }: { activeProjectPath: string }) {
  const { t } = useI18n()
  const location = useLocation()
  const [projects, setProjects] = useState<ProjectWithStatus[]>([])
  const [expanded, setExpanded] = useState(true)
  const isNewProjectPage = location.pathname === '/projects/new'

  const loadProjects = useCallback(async () => {
    try {
      const list = await api.getProjects()
      const enriched = await Promise.all(list.map(async p => {
        try {
          const audits = await api.getProjectAudits(p.id)
          return { ...p, status: projectStatus(audits) }
        } catch { return { ...p, status: 'unaudited' as ProjectStatus } }
      }))
      setProjects(enriched)
    } catch { /* silent */ }
  }, [])

  useEffect(() => { loadProjects() }, [location.pathname])

  // When on new-project page, hide completed projects
  const visible = isNewProjectPage ? projects.filter(p => p.status !== 'completed') : projects

  const statusBadge = (s: ProjectStatus) => {
    if (s === 'completed') return <CheckCircle2 className="w-3 h-3 text-green-500" />
    if (s === 'in_progress') return <RotateCcw className="w-3 h-3 text-accent animate-spin" />
    return <Circle className="w-3 h-3 text-text-dim" />
  }

  const statusText = (s: ProjectStatus) =>
    s === 'completed' ? t('nav.projectStatus.completed') :
    s === 'in_progress' ? t('nav.projectStatus.inProgress') : t('nav.projectStatus.unaudited')

  return (
    <div>
      {/* Projects toggle row */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm transition-all duration-150 text-text-muted hover:text-text hover:bg-bg-hover"
      >
        {expanded ? <ChevronDown className="w-3.5 h-3.5 text-text-dim" /> : <ChevronRight className="w-3.5 h-3.5 text-text-dim" />}
        <List className="w-4 h-4 text-text-dim" />
        <span className="flex-1 text-left">{t('nav.projects')}</span>
        <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-bg-hover text-text-muted">{visible.length}</span>
      </button>

      {/* Expanded project list */}
      {expanded && (
        <div className="mt-1 ml-5 pl-2 border-l border-border/60 space-y-0.5">
          {visible.length === 0 ? (
            <div className="px-2 py-1.5 text-[11px] text-text-dim">{t('nav.noProjects')}</div>
          ) : (
            visible.map(p => (
              <div
                key={p.id}
                className="group/project flex items-center gap-2 px-2 py-1.5 rounded-md text-xs transition-colors hover:bg-bg-hover"
                title={p.path}
              >
                <Link
                  to={`/projects/${p.id}`}
                  className={`flex items-center gap-2 flex-1 min-w-0 ${
                    activeProjectPath === p.id ? 'text-accent' : 'text-text-muted hover:text-text'
                  }`}
                >
                  <Folder className="w-3 h-3 shrink-0 text-text-dim" />
                  <span className="flex-1 truncate">{p.name}</span>
                  <span title={statusText(p.status)}>{statusBadge(p.status)}</span>
                </Link>
                {/* Delete button — visible on hover */}
                <button
                  onClick={async e => {
                    e.preventDefault()
                    e.stopPropagation()
                    if (!confirm(t('projects.delete'))) return
                    try {
                      await api.deleteProject(p.id)
                      await loadProjects()
                    } catch (err: any) {
                      alert(err.message || 'Delete failed')
                    }
                  }}
                  className="opacity-0 group-hover/project:opacity-100 text-text-dim hover:text-severity-high transition-all shrink-0 p-0.5"
                  title="Delete"
                >
                  <Trash2 className="w-3 h-3" />
                </button>
              </div>
            ))
          )}
        </div>
      )}

      {/* New project entry */}
      <Link
        to="/projects/new"
        className={`mt-0.5 flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm transition-all duration-150 ${
          isNewProjectPage ? 'bg-accent/10 text-accent font-medium' : 'text-text-muted hover:text-text hover:bg-bg-hover'
        }`}
      >
        <Plus className="w-4 h-4 text-text-dim" />
        <span className="flex-1">{t('nav.newProject')}</span>
      </Link>

      {isNewProjectPage && (
        <div className="mt-1 ml-5 pl-2 text-[10px] text-text-dim flex items-center gap-1">
          <Circle className="w-2 h-2" />
          {t('nav.hideCompleted')}
        </div>
      )}
    </div>
  )
}

function AppInner() {
  const location = useLocation()
  const { t, lang, toggle } = useI18n()
  const [projectId, setProjectId] = useState<string | null>(null)

  // Extract project id from /projects/:id route
  useEffect(() => {
    const m = location.pathname.match(/^\/projects\/([^/]+)$/)
    setProjectId(m ? m[1] : null)
  }, [location.pathname])

  return (
    <div className="h-screen flex overflow-hidden">
      {/* ── Sidebar (fixed, never scrolls) ─────────────────── */}
      <aside className="w-64 shrink-0 border-r border-border bg-bg-card flex flex-col">
        {/* Brand */}
        <div className="px-5 pt-5 pb-4">
          <Link to="/" className="flex items-center gap-3 group">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-accent/30 to-accent/10 border border-accent/30 flex items-center justify-center group-hover:border-accent/60 transition-colors">
              <Shield className="w-5 h-5 text-accent" />
            </div>
            <div>
              <div className="font-bold text-[15px] leading-tight">{t('app.name')}</div>
              <div className="text-[10px] text-text-muted mt-0.5 tracking-wide">{t('app.subtitle')}</div>
            </div>
          </Link>
        </div>

        {/* Nav */}
        <nav className="flex-1 overflow-y-auto px-3 py-2 space-y-4">
          {/* Overview group */}
          <div>
            <div className="px-3 mb-1.5 text-[10px] font-semibold uppercase tracking-widest text-text-dim">
              Overview
            </div>
            <div className="space-y-0.5">
              <NavLink
                to="/dashboard"
                icon={<LayoutDashboard className="w-4 h-4" />}
                label={t('nav.dashboard')}
                active={location.pathname === '/dashboard'}
              />
            </div>
          </div>

          {/* Projects group — expandable project list */}
          <div>
            <div className="px-3 mb-1.5 text-[10px] font-semibold uppercase tracking-widest text-text-dim">
              Projects
            </div>
            <ProjectSection activeProjectPath={projectId || ''} />
          </div>

          {/* System group */}
          <div>
            <div className="px-3 mb-1.5 text-[10px] font-semibold uppercase tracking-widest text-text-dim">
              System
            </div>
            <div className="space-y-0.5">
              <NavLink
                to="/skills"
                icon={<BookOpen className="w-4 h-4" />}
                label={t('nav.skills')}
                active={location.pathname.startsWith('/skills')}
              />
              <NavLink
                to="/mcp"
                icon={<Plug className="w-4 h-4" />}
                label={t('nav.mcp')}
                active={location.pathname.startsWith('/mcp')}
              />
              <NavLink
                to="/settings"
                icon={<KeyRound className="w-4 h-4" />}
                label={t('settings.title')}
                active={location.pathname.startsWith('/settings')}
              />
            </div>
          </div>
        </nav>

        {/* Bottom: runtime + lang + theme (fixed) */}
        <div className="p-3 border-t border-border bg-bg-card shrink-0">
          <div className="flex items-center justify-between px-1 mb-2">
            <div className="flex items-center gap-1.5 text-[11px] text-text-muted">
              <span className="relative flex w-2 h-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-500 opacity-60" />
                <span className="relative inline-flex rounded-full w-2 h-2 bg-green-500" />
              </span>
              {t('nav.runtime')}
            </div>
            <div className="flex items-center gap-0.5">
              <button
                onClick={toggle}
                className="flex items-center gap-1 text-[11px] text-text-muted hover:text-text px-1.5 py-1 rounded-md hover:bg-bg-hover transition-colors"
                title="Switch language"
              >
                <Languages className="w-3.5 h-3.5" />
                {lang === 'zh' ? 'EN' : '中文'}
              </button>
              <ThemeToggle />
            </div>
          </div>
          <div className="flex items-center justify-between px-1 pt-2 border-t border-border/60">
            <div className="flex items-center gap-1.5 text-[10px] text-text-dim">
              <Server className="w-3 h-3" />
              <span>localhost:8080</span>
            </div>
            <div className="flex items-center gap-1 text-[10px] text-text-dim">
              <Globe className="w-3 h-3" />
              <span>v1.1.0</span>
            </div>
          </div>
        </div>
      </aside>

      {/* ── Main content (only this scrolls) ───────────────── */}
      <main className="flex-1 overflow-y-auto h-full">
        <Routes>
          <Route path="/" element={<ProjectsPage />} />
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/projects/new" element={<ProjectsPage newMode />} />
          <Route path="/projects/:id" element={<ProjectDetailPage />} />
          <Route path="/audits/:id" element={<AuditDetailPage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="/skills" element={<SkillsPage />} />
          <Route path="/mcp" element={<MCPServersPage />} />
        </Routes>
      </main>
    </div>
  )
}

/* SafeLine-style nav item */
function NavLink({ to, icon, label, active }: { to: string; icon: React.ReactNode; label: string; active: boolean }) {
  return (
    <Link
      to={to}
      className={`group relative flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm transition-all duration-150 ${
        active ? 'bg-accent/10 text-accent font-medium' : 'text-text-muted hover:text-text hover:bg-bg-hover'
      }`}
    >
      {active && (
        <span className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-5 rounded-r-full bg-accent" />
      )}
      <span className={active ? 'text-accent' : 'text-text-dim group-hover:text-text-muted transition-colors'}>
        {icon}
      </span>
      <span className="flex-1">{label}</span>
      {active && <ChevronRight className="w-3.5 h-3.5 text-accent/60" />}
    </Link>
  )
}

function ThemeToggle() {
  const { theme, toggle } = useTheme()
  return (
    <button
      onClick={toggle}
      className="flex items-center gap-1 text-[11px] text-text-muted hover:text-text px-1.5 py-1 rounded-md hover:bg-bg-hover transition-colors"
      title={theme === 'dark' ? 'Switch to Light' : 'Switch to Dark'}
    >
      {theme === 'dark' ? (
        <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" />
        </svg>
      ) : (
        <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
        </svg>
      )}
    </button>
  )
}
