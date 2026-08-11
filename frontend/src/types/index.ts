export interface ProjectCreateParams {
  name: string
  path: string
  description?: string
  language?: string
}

export interface Project {
  id: string
  name: string
  path: string
  tech_stack: string[]
  description: string
  created_at?: string
  updated_at?: string
}

export interface Audit {
  id: string
  project_id: string
  mode: string
  status: string
  llm_provider: string
  llm_model: string
  turns_completed: number
  total_tokens: number
  total_tool_calls: number
  covered_files: string[]
  stage: string
  stages_completed: string[]
  scan_candidates_count: number
  error_message: string
  created_at?: string
  completed_at?: string
}

export interface Finding {
  id: string
  audit_id: string
  vulnerability_type: string
  severity: string
  title: string
  description: string
  file_path: string
  line_start: number
  line_end: number
  code_snippet: string
  source: string
  sink: string
  exploit_chain: string
  poc: string
  suggestion: string
  confidence: string
  cwe: string
  poc_verified: boolean | null
  needs_verification: boolean
  created_at?: string
}

export interface AuditLog {
  id: string
  audit_id: string
  turn: number
  role: string
  content: string
  tool_name: string
  tool_args: Record<string, unknown>
  tool_result: string
  tokens_used: number
  timestamp?: string
}

export interface LLMProviderInfo {
  provider: string
  configured: boolean
  default_model: string
}

export interface AuditCreateParams {
  project_id: string
  mode?: string
  llm_provider?: string
  llm_model?: string
  llm_api_key?: string
  llm_base_url?: string
  max_turns?: number
}

export interface DashboardStats {
  total_projects: number
  total_audits: number
  total_findings: number
  total_tokens: number
  total_tool_calls: number
  findings_by_severity: Record<string, number>
  findings_by_type: Record<string, number>
  audits_by_status: Record<string, number>
  recent_audits: RecentAudit[]
  severity_timeline: TimelineEntry[]
}

export interface RecentAudit {
  id: string
  project_name: string
  project_id: string
  status: string
  mode: string
  llm_provider: string
  findings_count: number
  turns: number
  tokens: number
  created_at: string | null
}

export interface TimelineEntry {
  audit_id: string
  created_at: string | null
  critical: number
  high: number
  medium: number
  low: number
}

export interface BatchAuditParams {
  project_ids: string[]
  mode?: string
  llm_provider?: string
  llm_model?: string
  llm_api_key?: string
  llm_base_url?: string
  max_turns?: number
}

export interface BatchAuditResult {
  started: string[]
  failed: { project_id: string; error: string }[]
}

export interface AuditCompareResult {
  audit_a_id: string
  audit_b_id: string
  only_in_a: Finding[]
  only_in_b: Finding[]
  common: Finding[]
}

export interface APIKey {
  id: string
  provider: string
  api_key: string
  base_url: string
  model: string
  label: string
  last_status: string   // unknown | ok | failed
  last_tested_at?: string | null
  last_error: string
  created_at?: string | null
  updated_at?: string | null
}

export interface APIKeyCreateParams {
  provider: string
  api_key: string
  base_url?: string
  model?: string
  label?: string
}

export interface SkillInfo {
  name: string
  display_name: string
  efficiency: number
  value_desc: string
  overview: string
  has_checklist: boolean
  checklist_langs: string[]
  enabled: boolean
  is_custom?: boolean
}

export interface MCPServerInfo {
  name: string
  url: string
  enabled: boolean
  description: string
  timeout: number
  has_auth: boolean
}

export interface MCPTestResult {
  status: string
  tools_count?: number
  latency_ms: number
  error?: string
  tools?: string[]
}

export interface MCPStats {
  configured_servers: number
  enabled_servers: number
  registered_tools: number
  calls_total: number
  calls_success: number
  calls_failed: number
}

export interface APIKeyTestResult {
  provider: string
  ok: boolean
  status: string   // ok | failed
  model: string
  message: string
  latency_ms: number
  tested_at?: string | null
}
