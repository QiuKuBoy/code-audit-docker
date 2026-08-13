import type {
  Project, Audit, Finding, AuditLog, LLMProviderInfo, AuditCreateParams,
  DashboardStats, BatchAuditParams, BatchAuditResult, AuditCompareResult,
  APIKey, APIKeyCreateParams, APIKeyTestResult,
  SkillInfo, MCPServerInfo, MCPTestResult, MCPStats,
} from '../types'

const BASE = '/api'

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    let msg = `HTTP ${res.status}`
    try { const body = await res.json(); msg = body.detail || msg } catch {}
    throw new Error(msg)
  }
  // Handle plain text responses (markdown report)
  const contentType = res.headers.get('content-type') || ''
  if (contentType.includes('text/plain')) {
    return await res.text() as unknown as T
  }
  return await res.json()
}

export const api = {
  // Projects
  getProjects: () => request<Project[]>('/projects'),
  getProject: (id: string) => request<Project>(`/projects/${id}`),
  createProject: (data: { name: string; path: string; description?: string; language?: string }) =>
    request<Project>('/projects', { method: 'POST', body: JSON.stringify(data) }),
  uploadProject: (file: File, meta: { name?: string; description?: string; language?: string }) => {
    const fd = new FormData()
    fd.append('file', file)
    fd.append('name', meta.name || '')
    fd.append('description', meta.description || '')
    fd.append('language', meta.language || '')
    // Bypass request() — FormData needs multipart, not application/json
    return fetch('/api/projects/upload', { method: 'POST', body: fd })
      .then(async res => {
        if (!res.ok) {
          const body = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }))
          throw new Error(body.detail || `HTTP ${res.status}`)
        }
        return res.json() as Promise<Project>
      })
  },
  cloneProject: (data: { url: string; name?: string; description?: string; language?: string }) =>
    request<Project>('/projects/clone', { method: 'POST', body: JSON.stringify(data) }),
  deleteProject: (id: string) => request<{ status: string }>(`/projects/${id}`, { method: 'DELETE' }),
  getProjectAudits: (id: string) => request<Audit[]>(`/projects/${id}/audits`),

  // Audits
  createAudit: (data: AuditCreateParams) =>
    request<{ audit_id: string; status: string }>('/audits', { method: 'POST', body: JSON.stringify(data) }),
  getAudit: (id: string) => request<Audit>(`/audits/${id}`),
  getAuditFindings: (id: string) => request<Finding[]>(`/audits/${id}/findings`),
  getAuditLogs: (id: string, limit?: number) =>
    request<AuditLog[]>(`/audits/${id}/logs${limit ? `?limit=${limit}` : ''}`),
  abortAudit: (id: string) => request<{ status: string }>(`/audits/${id}/abort`, { method: 'POST' }),
  resumeAudit: (id: string) => request<{ status: string }>(`/audits/${id}/resume`, { method: 'POST' }),
  exportReport: (id: string) => request<string>(`/audits/${id}/report`),
  exportSarif: (id: string) => request<string>(`/audits/${id}/sarif`),

  // Delete audits
  deleteAudit: (id: string) =>
    request<{ status: string; deleted_audits: number; deleted_findings: number; deleted_logs: number }>(
      `/audits/${id}`, { method: 'DELETE' }),
  batchDeleteAudits: (ids: string[]) =>
    request<{ deleted: string[]; failed: { audit_id: string; error: string }[]; deleted_count: number }>(
      '/audits/batch-delete', { method: 'POST', body: JSON.stringify({ audit_ids: ids }) }),

  // Batch audits
  createBatchAudits: (data: BatchAuditParams) =>
    request<BatchAuditResult>('/audits/batch', { method: 'POST', body: JSON.stringify(data) }),

  // Compare audits
  compareAudits: (aId: string, bId: string) => request<AuditCompareResult>(`/audits/${aId}/compare/${bId}`),

  // Dashboard
  getDashboardStats: () => request<DashboardStats>('/dashboard/stats'),

  // LLM
  getLLMProviders: () => request<LLMProviderInfo[]>('/llm/providers'),

  // API Keys
  listAPIKeys: () => request<APIKey[]>('/keys'),
  createAPIKey: (data: APIKeyCreateParams) =>
    request<APIKey>('/keys', { method: 'POST', body: JSON.stringify(data) }),
  updateAPIKey: (id: string, data: Partial<APIKeyCreateParams>) =>
    request<APIKey>(`/keys/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  deleteAPIKey: (id: string) =>
    request<{ deleted: { id: string; provider: string } }>(`/keys/${id}`, { method: 'DELETE' }),
  testAPIKey: (id: string) =>
    request<APIKeyTestResult>(`/keys/${id}/test`, { method: 'POST' }),
  testAPIKeyWithoutSaving: (data: APIKeyCreateParams) =>
    request<APIKeyTestResult>('/keys/test', { method: 'POST', body: JSON.stringify(data) }),

  // Skills
  listSkills: () => request<{ skills: SkillInfo[]; total: number }>('/skills'),
  getSkillDetail: (name: string) => request<{ name: string; content: string }>(`/skills/${name}`),
  createSkill: (data: { name: string; content: string; display_name?: string }) =>
    request<{ status: string; name: string }>('/skills', { method: 'POST', body: JSON.stringify(data) }),
  deleteSkill: (name: string) =>
    request<{ status: string; name: string }>(`/skills/${name}`, { method: 'DELETE' }),
  uploadSkill: (file: File) => {
    const fd = new FormData()
    fd.append('file', file)
    // Bypass request() — FormData needs multipart, not application/json
    return fetch('/api/skills/upload', { method: 'POST', body: fd })
      .then(async res => {
        if (!res.ok) {
          const body = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }))
          throw new Error(body.detail || `HTTP ${res.status}`)
        }
        return res.json()
      })
  },

  // MCP
  listMCPServers: () => request<{ servers: MCPServerInfo[]; total: number }>('/mcp/servers'),
  createMCPServer: (data: { name: string; url: string; headers?: Record<string, string>; timeout?: number; enabled?: boolean; description?: string }) =>
    request<{ status: string; name: string }>('/mcp/servers', { method: 'POST', body: JSON.stringify(data) }),
  deleteMCPServer: (name: string) =>
    request<{ status: string; name: string }>(`/mcp/servers/${name}`, { method: 'DELETE' }),
  testMCPServer: (name: string) =>
    request<MCPTestResult>(`/mcp/servers/${name}/test`, { method: 'POST' }),
  getMCPStats: () => request<MCPStats>('/mcp/stats'),
}
