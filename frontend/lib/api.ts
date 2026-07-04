export type Health = {
  api: string
  llm?: {
    ok?: boolean
    provider?: string
    model?: string
    error?: string
  }
  neo4j: boolean
  mode?: string
  llm_provider?: string
  sync?: SyncStatus
}

export type Stats = {
  entities: number
  facts: number
  documents: number
  chunks: number
  relations: number
  experiments?: number
  materials?: number
  publications?: number
  experts?: number
  facilities?: number
}

export type DocumentItem = {
  id: string
  name: string
  size: number
  status: 'processing' | 'paused' | 'completed' | 'failed' | 'canceled'
  error?: string | null
  uploaded_at: number
  chunks_total: number
  chunks_done: number
  chunks: number
  source_provider?: string | null
  source_path?: string | null
  source_url?: string | null
  sync_status?: string | null
  last_synced_at?: number | null
  uploaded_by?: string | null
}

export type DocumentDetails = DocumentItem & {
  mime?: string
  source_external_id?: string | null
  entities: { key: string; name: string; type: string; description?: string }[]
  facts: {
    subject: string
    predicate: string
    object: string
    value_min?: number | null
    value_max?: number | null
    unit?: string | null
    geography?: string
    confidence?: number
    quote?: string
  }[]
}

export type ChatFact = {
  subject: string
  predicate: string
  value: string
  geography: string
  confidence: number
  unit?: string
  source_doc?: string
}

export type RetrievalStats = {
  entities_found: number
  facts_found: number
  chunks_found: number
  hops: number
  cache_hit: boolean
  query_intent?: string
  constraints_detected?: number
}

export type ChatResponse = {
  answer: string
  sources: string[]
  facts: ChatFact[]
  confidence?: number
  cached: boolean
  mode?: 'production' | 'graph_rag' | 'cache' | 'demo'
  retrieval_stats?: RetrievalStats
}

export type ChatMessage = {
  id: string
  role: 'user' | 'assistant'
  content: string
  sources?: string[]
  facts?: ChatFact[]
  confidence?: number
  cached?: boolean
  error?: boolean
  created_at?: number
  mode?: 'production' | 'graph_rag' | 'cache' | 'demo'
  retrieval_stats?: RetrievalStats
}

export type SyncStatus = {
  name?: string
  enabled: boolean
  ok: boolean
  source_url?: string | null
  status?: string
  files_found?: number
  files_downloaded?: number
  files_skipped?: number
  files_failed?: number
  last_error?: string | null
  last_run_at?: number | null
}

export type Domain = {
  id: string
  name_ru: string
  name_en: string
  description: string
}

export type GraphNode = {
  key: string
  name: string
  type: string
  description?: string
  domains?: string[]
}

export type GraphLink = {
  source: string
  target: string
  type: string
}

export type GraphData = {
  nodes: GraphNode[]
  links: GraphLink[]
}

export type EntityDetails = {
  name: string
  type: string
  description?: string
  aliases?: string[]
  facts: {
    predicate?: string
    object?: string
    value_min?: number | null
    value_max?: number | null
    unit?: string | null
    geography?: string
    confidence?: number
    quote?: string
  }[]
  documents: string[]
  relations?: {
    type?: string
    direction?: 'in' | 'out'
    key?: string
    name?: string
    entity_type?: string
  }[]
}

export type CompareEntity = {
  key: string
  name: string
  type: string
}

export type CompareResult = {
  entity_a: CompareEntity
  entity_b: CompareEntity
  rows: { parameter: string; value_a: string; value_b: string; status: 'common' | 'only_a' | 'only_b' }[]
  stats: { facts_a: number; facts_b: number; parameters: number; common: number }
  analysis?: string | null
  analysis_error?: string | null
}

export type KnowledgeGap = {
  topic: string
  type: string
  description: string
  severity: 'low' | 'medium' | 'high'
  suggestion?: string
}

export type FactSearchResult = {
  subject: string
  predicate: string
  value: string
  unit?: string
  geography: string
  confidence: number
  source_doc?: string
  quote?: string
}

export type CacheStats = {
  total_entries: number
  hit_rate: number
  avg_similarity: number
  ttl_seconds: number
}

export type FactVersion = {
  id: string
  version_num: number
  fact_key: string
  subject: string
  predicate: string
  object: string
  value_min?: number | null
  value_max?: number | null
  unit?: string | null
  unit_normalized?: string | null
  geography?: string
  confidence?: number
  quote?: string
  source_doc?: string
  change_type: 'created' | 'corrected' | 'updated' | 'reverted'
  author: string
  comment?: string
  parent_version_id?: string
  created_at: number
}

export type EntityChange = {
  id: string
  change_type: string
  author: string
  comment?: string
  old_values?: Record<string, unknown>
  new_values?: Record<string, unknown>
  created_at: number
}

export type AuditEntry = {
  id: string
  action: string
  target_type: string
  target_key: string
  author: string
  details?: Record<string, unknown>
  timestamp: number
}

export type AuditStats = {
  total_entries: number
  by_action: Record<string, number>
  by_target_type: Record<string, number>
  by_author: Record<string, number>
  recent_activity: AuditEntry[]
}

export type DocumentVersion = {
  id: string
  change_type: string
  author: string
  comment?: string
  old_status?: string
  new_status?: string
  chunks_delta?: number
  created_at: number
}

export const ENTITY_TYPE_LABELS: Record<string, string> = {
  Material:    'Материал',
  Process:     'Процесс',
  Equipment:   'Оборудование',
  Property:    'Свойство',
  Experiment:  'Эксперимент',
  Publication: 'Публикация',
  Expert:      'Эксперт',
  Facility:    'Объект',
}

export const ENTITY_TYPE_COLORS: Record<string, string> = {
  Material:    'var(--color-chalk)',
  Process:     'var(--color-compass-gold)',
  Equipment:   'var(--color-chalk)',
  Property:    'var(--color-smoke)',
  Experiment:  'var(--color-compass-gold)',
  Publication: 'var(--color-smoke)',
  Expert:      'var(--color-chalk)',
  Facility:    'var(--color-smoke)',
}

export function getAuthToken(): string | null {
  if (typeof window === 'undefined') return null
  return localStorage.getItem('nornikel_token')
}

export function setAuthToken(token: string | null) {
  if (typeof window === 'undefined') return
  if (token) localStorage.setItem('nornikel_token', token)
  else localStorage.removeItem('nornikel_token')
}

export function getAuthHeaders(): Record<string, string> {
  const token = getAuthToken()
  return token ? { Authorization: `Bearer ${token}` } : {}
}

export type AuthUser = {
  id: string
  username: string
  role: string
  display_name: string
}

export async function fetchDomains(): Promise<Domain[]> {
  const res = await fetch('/api/domains', { headers: getAuthHeaders() })
  if (!res.ok) return []
  const data = await res.json()
  return data.domains || []
}

export async function fetcher<T>(url: string): Promise<T> {
  const res = await fetch(url, { headers: getAuthHeaders() })
  if (!res.ok) {
    const body = await res.json().catch(() => null)
    throw new Error(body?.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

export async function postJSON<T>(url: string, data: unknown): Promise<T> {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
    body: JSON.stringify(data),
  })
  if (!res.ok) {
    const body = await res.json().catch(() => null)
    throw new Error(body?.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

export async function deleteJSON<T>(url: string): Promise<T> {
  const res = await fetch(url, { method: 'DELETE' })
  if (!res.ok) {
    const body = await res.json().catch(() => null)
    throw new Error(body?.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

export async function uploadFile(
  file: File,
  signal?: AbortSignal,
): Promise<{ id: string; name: string; chunks: number; status: string }> {
  const fd = new FormData()
  fd.append('file', file)
  const res = await fetch('/api/documents/upload', { method: 'POST', body: fd, signal })
  if (!res.ok) {
    const body = await res.json().catch(() => null)
    throw new Error(body?.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

export async function importUrl(
  url: string,
  signal?: AbortSignal,
): Promise<{ id: string; name: string; chunks: number; status: string }> {
  const res = await fetch('/api/documents/import-url', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url }),
    signal,
  })
  if (!res.ok) {
    const body = await res.json().catch(() => null)
    throw new Error(body?.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

export const SUPPORTED_SOURCES: Record<string, string> = {
  'researchgate.net': 'ResearchGate',
  'www.researchgate.net': 'ResearchGate',
  'elibrary.ru': 'eLibrary',
  'www.elibrary.ru': 'eLibrary',
  'link.springer.com': 'Springer',
  'patents.google.com': 'Google Patents',
  'www.mdpi.com': 'MDPI',
  'cyberleninka.ru': 'CyberLeninka',
  'onlinelibrary.wiley.com': 'Wiley',
  'www.sciencedirect.com': 'ScienceDirect',
  'sciencedirect.com': 'ScienceDirect',
  'sci-hub.ru': 'Sci-Hub',
}

export async function controlDocument(
  id: string,
  action: 'pause' | 'resume' | 'cancel' | 'restart',
): Promise<{ ok: boolean; id: string; status: string }> {
  const res = await fetch(`/api/documents/${id}/${action}`, { method: 'POST' })
  if (!res.ok) {
    const body = await res.json().catch(() => null)
    throw new Error(body?.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

export async function getDocumentDetails(docId: string): Promise<DocumentDetails> {
  return fetcher(`/api/documents/${docId}/details`)
}

export async function controlSync(
  action: 'pause' | 'resume' | 'cancel' | 'restart',
): Promise<SyncStatus> {
  const res = await fetch(`/api/sync/${action}`, { method: 'POST' })
  if (!res.ok) {
    const body = await res.json().catch(() => null)
    throw new Error(body?.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

export async function searchFacts(params: {
  q: string
  geo?: string
  min_confidence?: number
  value_min?: number
  value_max?: number
  unit?: string
}): Promise<{ facts: FactSearchResult[] }> {
  const p = new URLSearchParams()
  p.set('q', params.q)
  if (params.geo) p.set('geo', params.geo)
  if (params.min_confidence !== undefined) p.set('min_confidence', String(params.min_confidence))
  if (params.value_min !== undefined) p.set('value_min', String(params.value_min))
  if (params.value_max !== undefined) p.set('value_max', String(params.value_max))
  if (params.unit) p.set('unit', params.unit)
  return fetcher(`/api/search/facts?${p}`)
}

export async function compareTopics(a: string, b: string): Promise<CompareResult> {
  return fetcher(`/api/compare?a=${encodeURIComponent(a)}&b=${encodeURIComponent(b)}`)
}

export async function getKnowledgeGaps(): Promise<{ gaps: KnowledgeGap[] }> {
  return fetcher('/api/gaps')
}

export async function getCacheStats(): Promise<CacheStats> {
  return fetcher('/api/chat/stats')
}

export async function clearCache(): Promise<{ ok: boolean; deleted: number }> {
  return deleteJSON('/api/cache')
}

export function formatBytes(n: number): string {
  if (!n) return '0 Б'
  if (n < 1024) return `${n} Б`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} КБ`
  return `${(n / 1024 / 1024).toFixed(1)} МБ`
}

export function formatConfidence(c: number): string {
  return `${Math.round(c * 100)}%`
}

export function geoLabel(geo: string): string {
  if (geo === 'RU') return '🇷🇺 РФ'
  if (geo === 'world') return '🌍 Мир'
  return '—'
}

export async function loginUser(username: string, password: string): Promise<{ token: string; user: AuthUser }> {
  const res = await fetch('/api/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  })
  if (!res.ok) {
    const body = await res.json().catch(() => null)
    throw new Error(body?.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

export async function registerUser(username: string, password: string, role: string = 'researcher', displayName: string = ''): Promise<AuthUser> {
  const res = await fetch('/api/auth/register', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password, role, display_name: displayName }),
  })
  if (!res.ok) {
    const body = await res.json().catch(() => null)
    throw new Error(body?.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

export async function getCurrentUser(): Promise<AuthUser> {
  return fetcher('/api/auth/me')
}

export async function getAuditStats(): Promise<AuditStats> {
  return fetcher('/api/audit/stats')
}

export async function revertFactVersion(
  factKey: string,
  versionId: string,
): Promise<{ version: FactVersion; message: string }> {
  const p = new URLSearchParams({ version_id: versionId })
  return postJSON(`/api/versions/fact/${encodeURIComponent(factKey)}/revert?${p}`, {})
}

export async function correctEntity(
  entityKey: string,
  data: { name?: string; description?: string; aliases?: string[]; comment?: string },
): Promise<{ entity_key: string; message: string }> {
  return postJSON(`/api/versions/entity/${encodeURIComponent(entityKey)}/correct`, data)
}

export async function getEntityHistory(entityKey: string): Promise<{ history: EntityChange[] }> {
  return fetcher(`/api/versions/entity/${encodeURIComponent(entityKey)}`)
}

export async function getDocumentVersions(docId: string): Promise<{ versions: DocumentVersion[] }> {
  return fetcher(`/api/versions/document/${encodeURIComponent(docId)}`)
}

export async function exportAuditLog(format: 'json' | 'csv', params?: {
  limit?: number
  target_type?: string
  author?: string
}): Promise<string> {
  const p = new URLSearchParams({ limit: String(params?.limit || 1000) })
  if (params?.target_type) p.set('target_type', params.target_type)
  if (params?.author) p.set('author', params.author)

  if (format === 'json') {
    const data = await fetcher<{ entries: AuditEntry[] }>(`/api/audit?${p}`)
    return JSON.stringify(data.entries, null, 2)
  }

  const data = await fetcher<{ entries: AuditEntry[] }>(`/api/audit?${p}`)
  const header = 'id,action,target_type,target_key,author,timestamp,details'
  const rows = data.entries.map(e =>
    [e.id, e.action, e.target_type, e.target_key, e.author, new Date(e.timestamp * 1000).toISOString(),
     JSON.stringify(e.details || {})].map(v => `"${String(v).replace(/"/g, '""')}"`).join(',')
  )
  return [header, ...rows].join('\n')
}

// ── JSON-LD Export helpers ──────────────────────────────────────

async function fetchJsonLd(url: string): Promise<object> {
  const res = await fetch(url)
  if (!res.ok) throw new Error(`Export failed: ${res.status}`)
  return res.json()
}

function downloadJsonLd(data: object, filename: string) {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/ld+json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

export async function exportJsonLdFull(limit = 500) {
  const data = await fetchJsonLd(`/api/export/jsonld?limit=${limit}`)
  downloadJsonLd(data, `nornikel-graph-${Date.now()}.jsonld`)
}

export async function exportJsonLdEntity(key: string) {
  const data = await fetchJsonLd(`/api/export/jsonld/entity/${encodeURIComponent(key)}`)
  downloadJsonLd(data, `nornikel-entity-${key}-${Date.now()}.jsonld`)
}

export async function exportJsonLdSubgraph(params: {
  search?: string
  type?: string
  limit?: number
  region?: string
  domain?: string
  min_confidence?: number
  year_from?: number
  year_to?: number
}) {
  const p = new URLSearchParams()
  if (params.search) p.set('search', params.search)
  if (params.type) p.set('type', params.type)
  if (params.limit) p.set('limit', String(params.limit))
  if (params.region) p.set('region', params.region)
  if (params.domain) p.set('domain', params.domain)
  if (params.min_confidence != null) p.set('min_confidence', String(params.min_confidence))
  if (params.year_from != null) p.set('year_from', String(params.year_from))
  if (params.year_to != null) p.set('year_to', String(params.year_to))
  const data = await fetchJsonLd(`/api/export/graph?${p}`)
  downloadJsonLd(data, `nornikel-subgraph-${Date.now()}.jsonld`)
}
