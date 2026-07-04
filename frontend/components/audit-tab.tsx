'use client'

import { useState, useEffect } from 'react'
import { createPortal } from 'react-dom'
import useSWR from 'swr'
import {
  ArrowDownToLine,
  ArrowLeftRight,
  ChevronRight,
  Clock,
  Database,
  Download,
  FileEdit,
  Files,
  History,
  Network,
  Pencil,
  RotateCcw,
  Shield,
  Trash2,
  User,
  Users,
  X,
} from 'lucide-react'
import {
  fetcher,
  postJSON,
  correctEntity,
  revertFactVersion,
  getAuditStats,
  getDocumentDetails,
  exportAuditLog,
  type AuditEntry,
  type AuditStats,
  type DocumentDetails,
  type FactVersion,
  type EntityChange,
  ENTITY_TYPE_LABELS,
  ENTITY_TYPE_COLORS,
} from '@/lib/api'

function formatTs(ts?: number) {
  if (!ts) return '—'
  return new Date(ts * 1000).toLocaleString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

const ACTION_LABELS: Record<string, string> = {
  fact_created: 'Факт создан',
  fact_corrected: 'Факт исправлен',
  fact_reverted: 'Факт откатён',
  entity_corrected: 'Сущность исправлена',
  entity_created: 'Сущность создана',
  document_uploaded: 'Документ загружен',
  document_completed: 'Документ обработан',
  document_paused: 'Документ приостановлен',
  document_resumed: 'Документ возобновлён',
  document_canceled: 'Документ отменён',
  document_failed: 'Ошибка документа',
  document_restarted: 'Документ перезапущен',
}

const ACTION_COLORS: Record<string, string> = {
  fact_created: '#3df2b4',
  fact_corrected: '#3df2b4',
  fact_reverted: '#3df2b4',
  entity_corrected: '#3df2b4',
  entity_created: '#3df2b4',
  document_uploaded: '#3df2b4',
  document_completed: '#3df2b4',
  document_paused: '#3df2b4',
  document_resumed: '#3df2b4',
  document_canceled: '#ef4444',
  document_failed: '#ef4444',
  document_restarted: '#3df2b4',
}

function formatBytes(n: number): string {
  if (!n) return '0 Б'
  if (n < 1024) return `${n} Б`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} КБ`
  return `${(n / 1024 / 1024).toFixed(1)} МБ`
}

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, { dot: string }> = {
    completed: { dot: '#3df2b4' },
    failed: { dot: '#ef4444' },
    canceled: { dot: '#ef4444' },
    paused: { dot: '#3df2b4' },
    processing: { dot: '#3df2b4' },
  }
  const resolved = map[status] || map.processing
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', fontSize: '12px' }}>
      <span style={{ width: '7px', height: '7px', borderRadius: '50%', background: resolved.dot }} />
      {status}
    </span>
  )
}

const inputStyle = {
  padding: '7px 10px',
  borderRadius: 0,
  border: '1px solid var(--border)',
  background: 'var(--surface)',
  color: 'var(--color-chalk)',
  fontSize: '13px',
  outline: 'none',
}

const labelStyle = {
  fontSize: '12px',
  fontWeight: 400 as const,
  color: 'var(--color-smoke)',
  display: 'block' as const,
  marginBottom: '4px',
}

// ── Audit Stats Summary ──────────────────────────────────
function AuditStatsPanel() {
  const { data, isLoading } = useSWR<AuditStats>('/api/audit/stats', fetcher, { refreshInterval: 30000 })

  if (isLoading || !data) return null

  const actionEntries = Object.entries(data.by_action).sort((a, b) => b[1] - a[1])
  const authorEntries = Object.entries(data.by_author).sort((a, b) => b[1] - a[1])

  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
        gap: '12px',
        marginBottom: '20px',
      }}
    >
      <div style={{ padding: '14px', background: 'var(--surface)', border: '1px solid var(--border)' }}>
        <div style={{ fontSize: '11px', color: 'var(--color-smoke)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
          Всего записей
        </div>
        <div style={{ fontSize: '24px', fontWeight: 400, color: 'var(--color-chalk)', marginTop: '4px' }}>
          {data.total_entries}
        </div>
      </div>

      <div style={{ padding: '14px', background: 'var(--surface)', border: '1px solid var(--border)' }}>
        <div style={{ fontSize: '11px', color: 'var(--color-smoke)', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: '8px' }}>
          По действиям
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '3px' }}>
          {actionEntries.slice(0, 5).map(([action, count]) => (
            <div key={action} style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px' }}>
              <span style={{ color: 'var(--color-smoke)' }}>{ACTION_LABELS[action] || action}</span>
              <span style={{ color: 'var(--color-chalk)', fontVariantNumeric: 'tabular-nums' }}>{count}</span>
            </div>
          ))}
        </div>
      </div>

      <div style={{ padding: '14px', background: 'var(--surface)', border: '1px solid var(--border)' }}>
        <div style={{ fontSize: '11px', color: 'var(--color-smoke)', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: '8px' }}>
          По авторам
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '3px' }}>
          {authorEntries.slice(0, 5).map(([author, count]) => (
            <div key={author} style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px' }}>
              <span style={{ color: 'var(--color-smoke)' }}>{author}</span>
              <span style={{ color: 'var(--color-chalk)', fontVariantNumeric: 'tabular-nums' }}>{count}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

// ── Document Detail Panel (from audit) ────────────────────
function AuditDocumentPanel({ docId, onClose }: { docId: string; onClose: () => void }) {
  const { data, isLoading, error } = useSWR<DocumentDetails>(
    `/api/documents/${docId}/details`,
    fetcher,
  )

  const factsBySubject: Record<string, NonNullable<DocumentDetails>['facts']> = {}
  if (data?.facts) {
    for (const f of data.facts) {
      const key = f.subject || '—'
      if (!factsBySubject[key]) factsBySubject[key] = []
      factsBySubject[key].push(f)
    }
  }

  const labelS = { fontSize: '11px', color: 'var(--color-smoke)', textTransform: 'uppercase' as const, letterSpacing: '0.5px' }
  const valueS = { fontSize: '13px', color: 'var(--color-chalk)', marginTop: '2px' }

  return createPortal(
    <div
      onClick={onClose}
      className="portal-backdrop-animated"
      style={{
        position: 'fixed', inset: 0, zIndex: 9999,
        background: 'rgba(0,0,0,0.5)',
        display: 'flex', justifyContent: 'flex-end',
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="portal-panel-animated"
        style={{
          width: '540px', maxWidth: '100vw', height: '100vh',
          background: 'var(--color-obsidian)', borderLeft: '1px solid var(--color-graphite)',
          display: 'flex', flexDirection: 'column', overflow: 'hidden',
        }}
      >
        <div style={{ padding: '20px 24px', borderBottom: '1px solid var(--color-graphite)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexShrink: 0 }}>
          <div>
            <div style={{ fontSize: '12px', color: 'var(--color-smoke)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Документ</div>
            <div style={{ fontSize: '18px', fontWeight: 400, marginTop: '4px', color: 'var(--color-chalk)' }}>
              {data?.name ? (
                <a
                  href={`/viewer?name=${encodeURIComponent(data.name)}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{
                    color: '#3df2b4',
                    textDecoration: 'none',
                    borderBottom: '1px dashed #3df2b4',
                    cursor: 'pointer',
                    transition: 'color 0.2s',
                  }}
                  onMouseEnter={e => e.currentTarget.style.color = '#ffffff'}
                  onMouseLeave={e => e.currentTarget.style.color = '#3df2b4'}
                >
                  {data.name}
                </a>
              ) : docId}
            </div>
          </div>
          <button onClick={onClose} style={{ background: 'none', border: 'none', color: 'var(--color-smoke)', cursor: 'pointer', padding: '8px' }}>
            <X size={18} />
          </button>
        </div>

        <div style={{ flex: 1, overflowY: 'auto', padding: '20px 24px' }}>
          {isLoading && <p style={{ color: 'var(--color-smoke)', fontSize: '13px' }}>Загрузка...</p>}
          {error && <p style={{ color: '#ef4444', fontSize: '13px' }}>Ошибка загрузки</p>}

          {data && (
            <>
              <div style={{ marginBottom: '24px' }}>
                <h3 style={{ fontSize: '13px', fontWeight: 400, color: 'var(--color-chalk)', marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <Database size={14} /> Техническая информация
                </h3>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', padding: '14px', background: 'var(--surface)', border: '1px solid var(--border)' }}>
                  <div><div style={labelS}>Название</div><div style={valueS}>{data.name}</div></div>
                  <div><div style={labelS}>Тип</div><div style={valueS}>{data.mime || '—'}</div></div>
                  <div><div style={labelS}>Размер</div><div style={valueS}>{formatBytes(data.size)}</div></div>
                  <div><div style={labelS}>Статус</div><div style={valueS}><StatusBadge status={data.status} /></div></div>
                  <div><div style={labelS}>Загружено</div><div style={valueS}>{formatTs(data.uploaded_at)}</div></div>
                  <div><div style={labelS}>Автор</div><div style={valueS}>{data.uploaded_by || 'system'}</div></div>
                  <div><div style={labelS}>Чанки</div><div style={valueS}>{data.chunks_done} / {data.chunks_total}</div></div>
                  <div><div style={labelS}>Источник</div><div style={valueS}>{data.source_provider || 'manual'}</div></div>
                  {data.source_url && <div style={{ gridColumn: '1 / -1' }}><div style={labelS}>URL</div><div style={{ ...valueS, wordBreak: 'break-all', fontSize: '12px' }}>{data.source_url}</div></div>}
                  {data.source_path && <div style={{ gridColumn: '1 / -1' }}><div style={labelS}>Путь</div><div style={{ ...valueS, wordBreak: 'break-all', fontSize: '12px' }}>{data.source_path}</div></div>}
                  {data.error && <div style={{ gridColumn: '1 / -1' }}><div style={labelS}>Ошибка</div><div style={{ ...valueS, color: '#ef4444' }}>{data.error}</div></div>}
                </div>
              </div>

              <div style={{ marginBottom: '24px' }}>
                <h3 style={{ fontSize: '13px', fontWeight: 400, color: 'var(--color-chalk)', marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <Network size={14} /> Связанные сущности ({data.entities?.length || 0})
                </h3>
                {!data.entities?.length ? (
                  <p style={{ color: 'var(--color-smoke)', fontSize: '13px' }}>Нет связанных сущностей</p>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                    {data.entities.map((e) => (
                      <div key={e.key} style={{ padding: '10px 12px', background: 'var(--surface)', border: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: '10px' }}>
                        <span style={{ fontSize: '10px', padding: '2px 6px', borderRadius: 0, background: 'var(--surface-2)', color: ENTITY_TYPE_COLORS[e.type] || 'var(--color-smoke)', whiteSpace: 'nowrap' }}>
                          {ENTITY_TYPE_LABELS[e.type] || e.type}
                        </span>
                        <span style={{ fontSize: '13px', color: 'var(--color-chalk)' }}>{e.name}</span>
                        {e.description && <span style={{ fontSize: '11px', color: 'var(--color-smoke)', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{e.description}</span>}
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <div>
                <h3 style={{ fontSize: '13px', fontWeight: 400, color: 'var(--color-chalk)', marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <FileEdit size={14} /> Факты ({data.facts?.length || 0})
                </h3>
                {!data.facts?.length ? (
                  <p style={{ color: 'var(--color-smoke)', fontSize: '13px' }}>Нет извлечённых фактов</p>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    {Object.entries(factsBySubject).map(([subject, facts]) => (
                      <div key={subject} style={{ padding: '12px', background: 'var(--surface)', border: '1px solid var(--border)' }}>
                        <div style={{ fontSize: '12px', fontWeight: 400, color: 'var(--color-chalk)', marginBottom: '8px' }}>{subject}</div>
                        <div style={{ display: 'grid', gap: '4px' }}>
                          {facts.map((f, i) => (
                            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '12px' }}>
                              <span style={{ color: 'var(--color-smoke)' }}>{f.predicate}</span>
                              <ChevronRight size={10} color="var(--color-smoke)" />
                              <span style={{ color: 'var(--color-chalk)' }}>{f.object}</span>
                              {f.confidence != null && (
                                <span style={{ marginLeft: 'auto', fontSize: '10px', padding: '1px 5px', background: 'var(--surface-2)', color: 'var(--color-smoke)', borderRadius: 0 }}>
                                  {Math.round(f.confidence * 100)}%
                                </span>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </div>,
    document.body
  )
}

// ── Audit Log Panel ──────────────────────────────────────
function AuditLogPanel() {
  const [authorFilter, setAuthorFilter] = useState('')
  const [actionFilter, setActionFilter] = useState('')
  const [targetFilter, setTargetFilter] = useState('')
  const [selectedDocId, setSelectedDocId] = useState<string | null>(null)

  const params = new URLSearchParams({ limit: '100' })
  if (authorFilter) params.set('author', authorFilter)
  if (actionFilter) params.set('action', actionFilter)
  if (targetFilter) params.set('target_type', targetFilter)

  const { data, isLoading } = useSWR<{ entries: AuditEntry[] }>(
    `/api/audit?${params.toString()}`,
    fetcher,
    { refreshInterval: 10000 },
  )

  const entries = data?.entries || []

  async function handleExport(format: 'json' | 'csv') {
    const content = await exportAuditLog(format, {
      limit: 1000,
      target_type: targetFilter || undefined,
      author: authorFilter || undefined,
    })
    const blob = new Blob([content], { type: format === 'json' ? 'application/json' : 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `audit-log.${format}`
    a.click()
    URL.revokeObjectURL(url)
  }

  function getEntryTitle(entry: AuditEntry): string {
    const d = entry.details || {}
    if (entry.target_type === 'document') {
      return String(d.doc_name || entry.target_key)
    }
    if (entry.target_type === 'fact') {
      const pred = d.predicate ? String(d.predicate) : ''
      const obj = d.object ? String(d.object) : ''
      return pred ? `${pred} → ${obj}` : entry.target_key
    }
    if (entry.target_type === 'entity') {
      return String(d.name || entry.target_key)
    }
    return entry.target_key
  }

  function getEntrySubtitle(entry: AuditEntry): string {
    const d = entry.details || {}
    const parts: string[] = []
    if (entry.target_type === 'document') {
      if (d.chunks_delta) parts.push(`${d.chunks_delta} чанков`)
      if (d.old_status && d.new_status) parts.push(`${d.old_status} → ${d.new_status}`)
      if (d.source_provider) parts.push(String(d.source_provider))
    }
    if (entry.target_type === 'fact') {
      if (d.version_num) parts.push(`v${d.version_num}`)
    }
    return parts.join(' · ')
  }

  return (
    <div>
      <div style={{ display: 'flex', gap: '10px', marginBottom: '16px', flexWrap: 'wrap', alignItems: 'center' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <User size={14} color="var(--color-smoke)" />
          <input
            placeholder="Автор..."
            value={authorFilter}
            onChange={(e) => setAuthorFilter(e.target.value)}
            style={{ ...inputStyle, width: '130px' }}
          />
        </div>
        <select value={actionFilter} onChange={(e) => setActionFilter(e.target.value)} style={inputStyle}>
          <option value="">Все действия</option>
          <option value="fact_created">Факт создан</option>
          <option value="fact_corrected">Факт исправлен</option>
          <option value="fact_reverted">Факт откатён</option>
          <option value="entity_corrected">Сущность исправлена</option>
          <option value="document_uploaded">Документ загружен</option>
          <option value="document_completed">Документ обработан</option>
        </select>
        <select value={targetFilter} onChange={(e) => setTargetFilter(e.target.value)} style={inputStyle}>
          <option value="">Все типы</option>
          <option value="fact">Факты</option>
          <option value="entity">Сущности</option>
          <option value="document">Документы</option>
        </select>

        <div style={{ marginLeft: 'auto', display: 'flex', gap: '6px' }}>
          <button onClick={() => handleExport('csv')} style={{ display: 'flex', alignItems: 'center', gap: '5px', padding: '6px 12px', fontSize: '12px', background: 'var(--surface)', border: '1px solid var(--border)', color: 'var(--color-smoke)', cursor: 'pointer', borderRadius: 0 }}>
            <Download size={12} /> CSV
          </button>
          <button onClick={() => handleExport('json')} style={{ display: 'flex', alignItems: 'center', gap: '5px', padding: '6px 12px', fontSize: '12px', background: 'var(--surface)', border: '1px solid var(--border)', color: 'var(--color-smoke)', cursor: 'pointer', borderRadius: 0 }}>
            <Download size={12} /> JSON
          </button>
        </div>
      </div>

      {isLoading && <p style={{ color: 'var(--color-smoke)', fontSize: '13px' }}>Загрузка...</p>}
      {entries.length === 0 && !isLoading && <p style={{ color: 'var(--color-smoke)', fontSize: '13px' }}>Журнал пуст</p>}

      <div style={{ display: 'grid', gap: '6px' }}>
        {entries.map((entry) => {
          const isDoc = entry.target_type === 'document'
          const title = getEntryTitle(entry)
          const subtitle = getEntrySubtitle(entry)
          return (
            <div
              key={entry.id}
              onClick={() => { if (isDoc) setSelectedDocId(entry.target_key) }}
              style={{
                display: 'flex', alignItems: 'flex-start', gap: '12px',
                padding: '12px 14px', borderRadius: 0,
                background: 'var(--surface)', border: '1px solid var(--border)',
                cursor: isDoc ? 'pointer' : 'default',
                transition: 'border-color 0.15s',
              }}
              onMouseEnter={(e) => { if (isDoc) e.currentTarget.style.borderColor = 'var(--color-chalk)' }}
              onMouseLeave={(e) => { if (isDoc) e.currentTarget.style.borderColor = 'var(--border)' }}
            >
              <div style={{ width: '8px', height: '8px', borderRadius: '50%', marginTop: '5px', flexShrink: 0, background: ACTION_COLORS[entry.action] || 'var(--color-smoke)' }} />
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                  <span style={{ fontWeight: 400, fontSize: '13px', color: 'var(--color-chalk)' }}>
                    {ACTION_LABELS[entry.action] || entry.action}
                  </span>
                  {isDoc ? (
                    <a
                      href={`/viewer?name=${encodeURIComponent(title)}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      onClick={(e) => e.stopPropagation()}
                      style={{
                        fontSize: '12px',
                        color: '#3df2b4',
                        textDecoration: 'none',
                        borderBottom: '1px dashed #3df2b4',
                        cursor: 'pointer',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                        maxWidth: '320px',
                        transition: 'color 0.2s',
                      }}
                      onMouseEnter={e => e.currentTarget.style.color = '#ffffff'}
                      onMouseLeave={e => e.currentTarget.style.color = '#3df2b4'}
                    >
                      {title}
                    </a>
                  ) : (
                    <span style={{ fontSize: '12px', color: 'var(--color-chalk)', fontWeight: 400, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '320px' }}>
                      {title}
                    </span>
                  )}
                  {isDoc && <Files size={12} color="var(--color-smoke)" />}
                </div>

                {subtitle && (
                  <div style={{ fontSize: '11px', color: 'var(--color-smoke)', marginTop: '3px', display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                    {subtitle.split(' · ').map((part, i) => (
                      <span key={i} style={{ padding: '1px 6px', background: 'var(--surface-2)', borderRadius: 0 }}>{part}</span>
                    ))}
                  </div>
                )}

                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '4px' }}>
                  <span style={{ fontSize: '12px', color: 'var(--color-smoke)' }}>
                    <User size={11} style={{ verticalAlign: '-1px', marginRight: '3px' }} />
                    {entry.author}
                  </span>
                  <span style={{ fontSize: '12px', color: 'var(--color-smoke)' }}>
                    <Clock size={11} style={{ verticalAlign: '-1px', marginRight: '3px' }} />
                    {formatTs(entry.timestamp)}
                  </span>
                  {!isDoc && (
                    <span style={{ fontSize: '11px', padding: '1px 6px', background: 'var(--surface-2)', color: 'var(--color-smoke)', borderRadius: 0 }}>
                      {entry.target_type}: {entry.target_key}
                    </span>
                  )}
                </div>

                {!!entry.details?.comment && (
                  <div style={{ fontSize: '12px', color: 'var(--color-smoke)', marginTop: '4px', fontStyle: 'italic' }}>
                    &laquo;{String(entry.details.comment)}&raquo;
                  </div>
                )}
              </div>
            </div>
          )
        })}
      </div>

      {selectedDocId && <AuditDocumentPanel docId={selectedDocId} onClose={() => setSelectedDocId(null)} />}
    </div>
  )
}

// ── Fact Version Diff View ───────────────────────────────
function FactVersionDiff({ versions, factKey }: { versions: FactVersion[]; factKey: string }) {
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [revertResult, setRevertResult] = useState<string | null>(null)
  const [reverting, setReverting] = useState(false)

  const selected = versions.find(v => v.id === selectedId)

  async function handleRevert(versionId: string) {
    setReverting(true)
    setRevertResult(null)
    try {
      const res = await revertFactVersion(factKey, versionId)
      setRevertResult(res.message)
    } catch (err) {
      setRevertResult(`Ошибка: ${err instanceof Error ? err.message : String(err)}`)
    } finally {
      setReverting(false)
    }
  }

  if (versions.length === 0) return null

  return (
    <div style={{ marginTop: '20px' }}>
      <h3 style={{ fontSize: '14px', fontWeight: 400, marginBottom: '10px', color: 'var(--color-chalk)' }}>
        <History size={14} style={{ verticalAlign: '-2px', marginRight: '6px' }} />
        Версии факта ({versions.length})
      </h3>

      {revertResult && (
        <div
          style={{
            marginBottom: '12px', padding: '10px 14px',
            background: revertResult.includes('Ошибка') ? 'rgba(239,68,68,0.08)' : 'rgba(34,197,94,0.08)',
            border: `1px solid ${revertResult.includes('Ошибка') ? 'rgba(239,68,68,0.2)' : 'rgba(34,197,94,0.2)'}`,
            color: revertResult.includes('Ошибка') ? '#ef4444' : '#22c55e',
            fontSize: '13px',
          }}
        >
          {revertResult}
        </div>
      )}

      <div style={{ display: 'grid', gap: '6px' }}>
        {versions.map((v, idx) => {
          const isSelected = v.id === selectedId
          const prev = versions[idx + 1]
          return (
            <div key={v.id}>
              <div
                onClick={() => setSelectedId(isSelected ? null : v.id)}
                style={{
                  display: 'flex', alignItems: 'center', gap: '10px',
                  padding: '10px 12px', cursor: 'pointer',
                  background: isSelected ? 'var(--surface-2)' : 'var(--surface)',
                  border: `1px solid ${isSelected ? 'var(--color-chalk)' : 'var(--border)'}`,
                  fontSize: '13px', borderRadius: 0,
                }}
              >
                <span
                  style={{
                    fontWeight: 400, fontSize: '11px', padding: '2px 7px', borderRadius: 0,
                    background: v.change_type === 'reverted' ? 'rgba(168,85,247,0.15)' : 'var(--surface-2)',
                    color: v.change_type === 'reverted' ? '#a855f7' : 'var(--color-smoke)',
                    minWidth: '28px', textAlign: 'center',
                  }}
                >
                  v{v.version_num}
                </span>
                <span style={{ flex: 1, color: 'var(--color-chalk)' }}>
                  {v.predicate} &rarr; {v.object}
                </span>
                <span style={{ fontSize: '11px', padding: '1px 6px', borderRadius: 0, background: 'var(--surface-2)', color: 'var(--color-smoke)' }}>
                  {v.change_type}
                </span>
                <span style={{ fontSize: '11px', color: 'var(--color-smoke)' }}>
                  {v.author} &middot; {formatTs(v.created_at)}
                </span>
              </div>

              {isSelected && (
                <div style={{ padding: '12px 14px', background: 'var(--surface-2)', border: '1px solid var(--border)', borderTop: 'none', borderRadius: 0 }}>
                  <div style={{ display: 'grid', gridTemplateColumns: prev ? '1fr 40px 1fr' : '1fr', gap: '8px', fontSize: '12px' }}>
                    {prev && (
                      <div>
                        <div style={{ color: 'var(--color-smoke)', marginBottom: '6px', fontWeight: 400 }}>
                          <ArrowLeftRight size={11} style={{ verticalAlign: '-1px', marginRight: '4px' }} />
                          Предыдущая версия (v{prev.version_num})
                        </div>
                        <div style={{ color: 'var(--color-smoke)' }}>Предикат: <span style={{ color: 'var(--color-chalk)' }}>{prev.predicate}</span></div>
                        <div style={{ color: 'var(--color-smoke)' }}>Значение: <span style={{ color: 'var(--color-chalk)' }}>{prev.object}</span></div>
                        <div style={{ color: 'var(--color-smoke)' }}>Уверенность: <span style={{ color: 'var(--color-chalk)' }}>{prev.confidence ? `${Math.round(prev.confidence * 100)}%` : '—'}</span></div>
                      </div>
                    )}
                    {prev && (
                      <div style={{ display: 'flex', justifyContent: 'center', paddingTop: '20px' }}>
                        <ArrowLeftRight size={16} color="var(--color-smoke)" />
                      </div>
                    )}
                    <div>
                      <div style={{ color: 'var(--color-smoke)', marginBottom: '6px', fontWeight: 400 }}>
                        Текущая версия (v{v.version_num})
                      </div>
                      <div style={{ color: 'var(--color-smoke)' }}>Предикат: <span style={{ color: 'var(--color-chalk)' }}>{v.predicate}</span></div>
                      <div style={{ color: 'var(--color-smoke)' }}>Значение: <span style={{ color: 'var(--color-chalk)' }}>{v.object}</span></div>
                      <div style={{ color: 'var(--color-smoke)' }}>Уверенность: <span style={{ color: 'var(--color-chalk)' }}>{v.confidence ? `${Math.round(v.confidence * 100)}%` : '—'}</span></div>
                      {v.comment && <div style={{ color: 'var(--color-smoke)', marginTop: '4px', fontStyle: 'italic' }}>&laquo;{v.comment}&raquo;</div>}
                    </div>
                  </div>

                  {idx < versions.length - 1 && (
                    <div style={{ marginTop: '10px', paddingTop: '10px', borderTop: '1px solid var(--border)' }}>
                      <button
                        onClick={(e) => { e.stopPropagation(); handleRevert(v.id) }}
                        disabled={reverting}
                        style={{
                          display: 'flex', alignItems: 'center', gap: '5px',
                          padding: '6px 12px', fontSize: '12px',
                          background: 'rgba(168,85,247,0.1)', border: '1px solid rgba(168,85,247,0.3)',
                          color: '#a855f7', cursor: 'pointer', borderRadius: 0,
                        }}
                      >
                        <RotateCcw size={12} /> {reverting ? 'Откат...' : `Откатить к v${v.version_num}`}
                      </button>
                    </div>
                  )}
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ── Fact Correction Panel ────────────────────────────────
function FactCorrectionPanel() {
  const [factKey, setFactKey] = useState('')
  const [predicate, setPredicate] = useState('')
  const [objectVal, setObjectVal] = useState('')
  const [author, setAuthor] = useState('')
  const [comment, setComment] = useState('')
  const [result, setResult] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const { data: versionsData, mutate: mutateVersions } = useSWR<{ versions: FactVersion[] }>(
    factKey.trim() ? `/api/versions/fact/${encodeURIComponent(factKey.trim())}` : null,
    fetcher,
  )
  const versions = versionsData?.versions || []

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!factKey.trim()) return
    setLoading(true)
    setResult(null)
    try {
      const res = await postJSON<{ message: string; version?: { version_num: number } }>(
        `/api/versions/fact/${encodeURIComponent(factKey.trim())}/correct`,
        {
          ...(predicate && { predicate }),
          ...(objectVal && { object: objectVal }),
          author: author || 'expert',
          comment,
        },
      )
      setResult(res.message)
      setPredicate('')
      setObjectVal('')
      setComment('')
      mutateVersions()
    } catch (err) {
      setResult(`Ошибка: ${err instanceof Error ? err.message : String(err)}`)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <form onSubmit={handleSubmit} style={{ display: 'grid', gap: '10px', maxWidth: '500px' }}>
        <div>
          <label style={labelStyle}>Ключ факта *</label>
          <input
            value={factKey}
            onChange={(e) => setFactKey(e.target.value)}
            placeholder="например: nickel_electrowinning_flow_rate"
            required
            style={{ width: '100%', ...inputStyle }}
          />
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
          <div>
            <label style={labelStyle}>Предикат</label>
            <input
              value={predicate}
              onChange={(e) => setPredicate(e.target.value)}
              placeholder="имеет скорость потока"
              style={{ width: '100%', ...inputStyle }}
            />
          </div>
          <div>
            <label style={labelStyle}>Значение</label>
            <input
              value={objectVal}
              onChange={(e) => setObjectVal(e.target.value)}
              placeholder="от 0.5 до 2.0 м/с"
              style={{ width: '100%', ...inputStyle }}
            />
          </div>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
          <div>
            <label style={labelStyle}>Автор</label>
            <input
              value={author}
              onChange={(e) => setAuthor(e.target.value)}
              placeholder="Иванов И.И."
              style={{ width: '100%', ...inputStyle }}
            />
          </div>
          <div>
            <label style={labelStyle}>Комментарий</label>
            <input
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              placeholder="Уточнение по данным..."
              style={{ width: '100%', ...inputStyle }}
            />
          </div>
        </div>
        <button
          type="submit"
          disabled={loading || !factKey.trim()}
          className="btn-primary"
          style={{ width: 'fit-content', padding: '9px 18px' }}
        >
          <Pencil size={14} /> {loading ? 'Сохранение...' : 'Сохранить исправление'}
        </button>
      </form>

      {result && (
        <div
          style={{
            marginTop: '12px', padding: '10px 14px', borderRadius: 0,
            background: result.startsWith('Ошибка') ? 'rgba(239,68,68,0.08)' : 'rgba(34,197,94,0.08)',
            border: `1px solid ${result.startsWith('Ошибка') ? 'rgba(239,68,68,0.2)' : 'rgba(34,197,94,0.2)'}`,
            color: result.startsWith('Ошибка') ? '#ef4444' : '#22c55e',
            fontSize: '13px',
          }}
        >
          {result}
        </div>
      )}

      <FactVersionDiff versions={versions} factKey={factKey.trim()} />
    </div>
  )
}

// ── Entity Correction Panel ──────────────────────────────
function EntityCorrectionPanel() {
  const [entityKey, setEntityKey] = useState('')
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [aliases, setAliases] = useState('')
  const [author, setAuthor] = useState('')
  const [comment, setComment] = useState('')
  const [result, setResult] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const { data: historyData } = useSWR<{ history: EntityChange[] }>(
    entityKey.trim() ? `/api/versions/entity/${encodeURIComponent(entityKey.trim())}` : null,
    fetcher,
  )
  const history = historyData?.history || []

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!entityKey.trim()) return
    setLoading(true)
    setResult(null)
    try {
      const res = await correctEntity(entityKey.trim(), {
        ...(name && { name }),
        ...(description && { description }),
        ...(aliases && { aliases: aliases.split(',').map(a => a.trim()).filter(Boolean) }),
        comment,
      })
      setResult(res.message)
      setName('')
      setDescription('')
      setAliases('')
      setComment('')
    } catch (err) {
      setResult(`Ошибка: ${err instanceof Error ? err.message : String(err)}`)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <form onSubmit={handleSubmit} style={{ display: 'grid', gap: '10px', maxWidth: '500px' }}>
        <div>
          <label style={labelStyle}>Ключ сущности *</label>
          <input
            value={entityKey}
            onChange={(e) => setEntityKey(e.target.value)}
            placeholder="например: a1b2c3d4e5f6"
            required
            style={{ width: '100%', ...inputStyle }}
          />
        </div>
        <div>
          <label style={labelStyle}>Название</label>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="новое название сущности"
            style={{ width: '100%', ...inputStyle }}
          />
        </div>
        <div>
          <label style={labelStyle}>Описание</label>
          <input
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="обновлённое описание"
            style={{ width: '100%', ...inputStyle }}
          />
        </div>
        <div>
          <label style={labelStyle}>Алиасы (через запятую)</label>
          <input
            value={aliases}
            onChange={(e) => setAliases(e.target.value)}
            placeholder="синоним1, синоним2"
            style={{ width: '100%', ...inputStyle }}
          />
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
          <div>
            <label style={labelStyle}>Автор</label>
            <input
              value={author}
              onChange={(e) => setAuthor(e.target.value)}
              placeholder="Иванов И.И."
              style={{ width: '100%', ...inputStyle }}
            />
          </div>
          <div>
            <label style={labelStyle}>Комментарий</label>
            <input
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              placeholder="Причина исправления..."
              style={{ width: '100%', ...inputStyle }}
            />
          </div>
        </div>
        <button
          type="submit"
          disabled={loading || !entityKey.trim()}
          className="btn-primary"
          style={{ width: 'fit-content', padding: '9px 18px' }}
        >
          <Pencil size={14} /> {loading ? 'Сохранение...' : 'Сохранить исправление'}
        </button>
      </form>

      {result && (
        <div
          style={{
            marginTop: '12px', padding: '10px 14px', borderRadius: 0,
            background: result.startsWith('Ошибка') ? 'rgba(239,68,68,0.08)' : 'rgba(34,197,94,0.08)',
            border: `1px solid ${result.startsWith('Ошибка') ? 'rgba(239,68,68,0.2)' : 'rgba(34,197,94,0.2)'}`,
            color: result.startsWith('Ошибка') ? '#ef4444' : '#22c55e',
            fontSize: '13px',
          }}
        >
          {result}
        </div>
      )}

      {history.length > 0 && (
        <div style={{ marginTop: '20px' }}>
          <h3 style={{ fontSize: '14px', fontWeight: 400, marginBottom: '10px', color: 'var(--color-chalk)' }}>
            <History size={14} style={{ verticalAlign: '-2px', marginRight: '6px' }} />
            История изменений ({history.length})
          </h3>
          <div style={{ display: 'grid', gap: '6px' }}>
            {history.map((h) => (
              <div
                key={h.id}
                style={{
                  padding: '10px 12px', borderRadius: 0,
                  background: 'var(--surface)', border: '1px solid var(--border)',
                  fontSize: '13px',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span style={{ fontSize: '11px', padding: '2px 7px', borderRadius: 0, background: 'var(--surface-2)', color: 'var(--color-smoke)' }}>
                    {h.change_type}
                  </span>
                  <span style={{ color: 'var(--color-chalk)' }}>
                    {h.author}
                  </span>
                  <span style={{ fontSize: '11px', color: 'var(--color-smoke)' }}>
                    {formatTs(h.created_at)}
                  </span>
                </div>
                {h.comment && (
                  <div style={{ fontSize: '12px', color: 'var(--color-smoke)', marginTop: '4px', fontStyle: 'italic' }}>
                    &laquo;{h.comment}&raquo;
                  </div>
                )}
                {h.old_values && Object.keys(h.old_values).length > 0 && h.new_values && Object.keys(h.new_values).length > 0 && (
                  <div style={{ marginTop: '6px', display: 'grid', gridTemplateColumns: '1fr 40px 1fr', gap: '6px', fontSize: '11px' }}>
                    <div style={{ color: 'var(--color-smoke)' }}>
                      {Object.entries(h.old_values).map(([k, v]) => (
                        <div key={k}>{k}: <span style={{ color: 'var(--color-chalk)' }}>{String(v)}</span></div>
                      ))}
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'center' }}>
                      <ArrowLeftRight size={12} color="var(--color-smoke)" />
                    </div>
                    <div style={{ color: 'var(--color-smoke)' }}>
                      {Object.entries(h.new_values).map(([k, v]) => (
                        <div key={k}>{k}: <span style={{ color: 'var(--color-chalk)' }}>{String(v)}</span></div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

// ── Main Audit Tab ───────────────────────────────────────
export function AuditTab() {
  const [panel, setPanel] = useState<'log' | 'fact-correct' | 'entity-correct'>('log')

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      <AuditStatsPanel />

      <div style={{ display: 'inline-flex', border: '1px solid var(--color-graphite)', flexWrap: 'wrap' }}>
        <button
          type="button"
          className="toolbar-btn"
          onClick={() => setPanel('log')}
          style={{
            background: panel === 'log' ? 'var(--color-carbon)' : 'transparent',
            color: panel === 'log' ? 'var(--color-chalk)' : 'var(--color-smoke)',
          }}
        >
          <Shield size={13} style={{ verticalAlign: '-2px', marginRight: '5px' }} />
          Журнал аудита
        </button>
        <div style={{ width: '1px', background: 'var(--color-graphite)' }} />
        <button
          type="button"
          className="toolbar-btn"
          onClick={() => setPanel('fact-correct')}
          style={{
            background: panel === 'fact-correct' ? 'var(--color-carbon)' : 'transparent',
            color: panel === 'fact-correct' ? 'var(--color-chalk)' : 'var(--color-smoke)',
          }}
        >
          <FileEdit size={13} style={{ verticalAlign: '-2px', marginRight: '5px' }} />
          Исправление фактов
        </button>
        <div style={{ width: '1px', background: 'var(--color-graphite)' }} />
        <button
          type="button"
          className="toolbar-btn"
          onClick={() => setPanel('entity-correct')}
          style={{
            background: panel === 'entity-correct' ? 'var(--color-carbon)' : 'transparent',
            color: panel === 'entity-correct' ? 'var(--color-chalk)' : 'var(--color-smoke)',
          }}
        >
          <Users size={13} style={{ verticalAlign: '-2px', marginRight: '5px' }} />
          Исправление сущностей
        </button>
      </div>

      {panel === 'log' && <AuditLogPanel />}
      {panel === 'fact-correct' && <FactCorrectionPanel />}
      {panel === 'entity-correct' && <EntityCorrectionPanel />}
    </div>
  )
}
