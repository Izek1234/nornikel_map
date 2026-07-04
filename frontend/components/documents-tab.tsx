'use client'

import type { ReactNode } from 'react'
import { useCallback, useMemo, useRef, useState } from 'react'
import useSWR from 'swr'
import { Cloud, Database, FileUp, Files, Link, RefreshCw, ScanSearch, X, ChevronRight, Network, BookOpen } from 'lucide-react'
import {
  controlDocument,
  controlSync,
  fetcher,
  formatBytes,
  getDocumentDetails,
  importUrl,
  uploadFile,
  type DocumentDetails,
  type DocumentItem,
  type Health,
  type SyncStatus,
  ENTITY_TYPE_LABELS,
  ENTITY_TYPE_COLORS,
} from '@/lib/api'

const STATUS_LABELS: Record<string, string> = {
  processing: 'В обработке',
  paused: 'На паузе',
  completed: 'Готово',
  failed: 'Ошибка',
  canceled: 'Ошибка',
}

const TASK_LABELS: Record<UploadTask['status'], string> = {
  queued: 'В очереди',
  uploading: 'Загрузка',
  stopped: 'Остановлен',
  failed: 'Ошибка',
  processing: 'Передан в обработку',
}

type UploadTask = {
  id: string
  file: File
  name: string
  size: number
  status: 'queued' | 'uploading' | 'stopped' | 'failed' | 'processing'
  error?: string | null
  remoteId?: string
}



function StatusBadge({ status }: { status: string }) {
  const map: Record<string, { color: string; bg: string; border: string; dot: string }> = {
    completed: { color: 'var(--color-smoke)', bg: '#1a1a1a', border: 'var(--color-graphite)', dot: '#98ff38' },
    failed: { color: 'var(--color-smoke)', bg: '#1a1a1a', border: 'var(--color-graphite)', dot: '#ef4444' },
    canceled: { color: 'var(--color-smoke)', bg: '#1a1a1a', border: 'var(--color-graphite)', dot: '#ef4444' },
    paused: { color: 'var(--color-smoke)', bg: '#1a1a1a', border: 'var(--color-graphite)', dot: '#fde68a' },
    processing: { color: 'var(--color-smoke)', bg: '#1a1a1a', border: 'var(--color-graphite)', dot: '#6f6759' },
  }
  const resolved = map[status] || map.processing

  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '8px',
        padding: '6px 10px',
        borderRadius: 0,
        border: `1px solid ${resolved.border}`,
        background: resolved.bg,
        color: resolved.color,
        fontSize: '12px',
        fontWeight: 400,
      }}
    >
      <span style={{ width: '7px', height: '7px', borderRadius: '50%', background: resolved.dot }} />
      {STATUS_LABELS[status] || status}
    </span>
  )
}

function ActionButton({
  children,
  onClick,
  disabled,
  primary = false,
}: {
  children: ReactNode
  onClick?: () => void
  disabled?: boolean
  primary?: boolean
}) {
  return (
    <button type="button" className={primary ? 'btn-primary upload-primary' : 'btn-ghost'} disabled={disabled} onClick={onClick}>
      {children}
    </button>
  )
}

function MetricCard({ icon, label, value }: { icon: ReactNode; label: string; value: string | number }) {
  return (
    <div className="depot-card" style={{ padding: '18px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--color-smoke)', fontSize: '12px' }}>
        {icon}
        {label}
      </div>
      <div style={{ marginTop: '8px', fontSize: '26px', fontWeight: 400 }}>{value}</div>
    </div>
  )
}

function formatTs(ts?: number) {
  if (!ts) return '—'
  return new Date(ts * 1000).toLocaleString('ru-RU', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}

function DocumentDetailPanel({ docId, onClose }: { docId: string; onClose: () => void }) {
  const { data, isLoading, error } = useSWR<DocumentDetails>(
    `/api/documents/${docId}/details`,
    fetcher,
    { refreshInterval: 10000 },
  )

  const factsBySubject = useMemo(() => {
    if (!data?.facts) return {}
    const grouped: Record<string, typeof data.facts> = {}
    for (const f of data.facts) {
      const key = f.subject || '—'
      if (!grouped[key]) grouped[key] = []
      grouped[key].push(f)
    }
    return grouped
  }, [data?.facts])

  const labelStyle = { fontSize: '11px', color: 'var(--color-smoke)', textTransform: 'uppercase' as const, letterSpacing: '0.5px' }
  const valueStyle = { fontSize: '13px', color: 'var(--color-chalk)', marginTop: '2px' }

  return (
    <div style={{
      position: 'fixed', top: 0, right: 0, bottom: 0, width: '520px', maxWidth: '100vw',
      background: 'var(--color-obsidian)', borderLeft: '1px solid var(--color-graphite)',
      zIndex: 100, display: 'flex', flexDirection: 'column', overflow: 'hidden',
    }}>
      {/* Header */}
      <div style={{ padding: '20px 24px', borderBottom: '1px solid var(--color-graphite)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexShrink: 0 }}>
        <div>
          <div style={{ fontSize: '12px', color: 'var(--color-smoke)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Документ</div>
          <div style={{ fontSize: '18px', fontWeight: 400, marginTop: '4px', color: 'var(--color-chalk)' }}>
            {data?.name || docId}
          </div>
        </div>
        <button onClick={onClose} style={{ background: 'none', border: 'none', color: 'var(--color-smoke)', cursor: 'pointer', padding: '8px' }}>
          <X size={18} />
        </button>
      </div>

      {/* Content */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '20px 24px' }}>
        {isLoading && <p style={{ color: 'var(--color-smoke)', fontSize: '13px' }}>Загрузка...</p>}
        {error && <p style={{ color: '#ef4444', fontSize: '13px' }}>Ошибка загрузки</p>}

        {data && (
          <>
            {/* Technical Info */}
            <div style={{ marginBottom: '24px' }}>
              <h3 style={{ fontSize: '13px', fontWeight: 400, color: 'var(--color-chalk)', marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                <Database size={14} /> Техническая информация
              </h3>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', padding: '14px', background: 'var(--surface)', border: '1px solid var(--border)' }}>
                <div>
                  <div style={labelStyle}>Название</div>
                  <div style={valueStyle}>{data.name}</div>
                </div>
                <div>
                  <div style={labelStyle}>Тип</div>
                  <div style={valueStyle}>{data.mime || '—'}</div>
                </div>
                <div>
                  <div style={labelStyle}>Размер</div>
                  <div style={valueStyle}>{formatBytes(data.size)}</div>
                </div>
                <div>
                  <div style={labelStyle}>Статус</div>
                  <div style={valueStyle}><StatusBadge status={data.status} /></div>
                </div>
                <div>
                  <div style={labelStyle}>Загружено</div>
                  <div style={valueStyle}>{formatTs(data.uploaded_at)}</div>
                </div>
                <div>
                  <div style={labelStyle}>Автор</div>
                  <div style={valueStyle}>{data.uploaded_by || 'system'}</div>
                </div>
                <div>
                  <div style={labelStyle}>Чанки</div>
                  <div style={valueStyle}>{data.chunks_done} / {data.chunks_total}</div>
                </div>
                <div>
                  <div style={labelStyle}>Источник</div>
                  <div style={valueStyle}>{data.source_provider || 'manual'}</div>
                </div>
                {data.source_url && (
                  <div style={{ gridColumn: '1 / -1' }}>
                    <div style={labelStyle}>URL</div>
                    <div style={{ ...valueStyle, wordBreak: 'break-all', fontSize: '12px' }}>{data.source_url}</div>
                  </div>
                )}
                {data.error && (
                  <div style={{ gridColumn: '1 / -1' }}>
                    <div style={labelStyle}>Ошибка</div>
                    <div style={{ ...valueStyle, color: '#ef4444' }}>{data.error}</div>
                  </div>
                )}
              </div>
            </div>

            {/* Entities */}
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
                      <span style={{
                        fontSize: '10px', padding: '2px 6px', borderRadius: 0,
                        background: 'var(--surface-2)', color: ENTITY_TYPE_COLORS[e.type] || 'var(--color-smoke)',
                        whiteSpace: 'nowrap',
                      }}>
                        {ENTITY_TYPE_LABELS[e.type] || e.type}
                      </span>
                      <span style={{ fontSize: '13px', color: 'var(--color-chalk)' }}>{e.name}</span>
                      {e.description && (
                        <span style={{ fontSize: '11px', color: 'var(--color-smoke)', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {e.description}
                        </span>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Facts */}
            <div>
              <h3 style={{ fontSize: '13px', fontWeight: 400, color: 'var(--color-chalk)', marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                <BookOpen size={14} /> Факты ({data.facts?.length || 0})
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
  )
}

function SyncPanel({
  sync,
  syncAction,
  onAction,
}: {
  sync: SyncStatus
  syncAction: string | null
  onAction: (action: 'pause' | 'resume' | 'cancel' | 'restart') => void
}) {
  const filesFound = sync.files_found ?? 0
  const done = (sync.files_downloaded ?? 0) + (sync.files_skipped ?? 0)
  const pct = filesFound > 0 ? Math.round((done / filesFound) * 100) : 0

  return (
    <div className="depot-card" style={{ padding: '20px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: '16px', flexWrap: 'wrap', alignItems: 'center' }}>
        <div>
          <div style={{ color: 'var(--color-smoke)', fontSize: '12px', fontWeight: 400, letterSpacing: '0.08em', textTransform: 'uppercase' }}>
            Yandex Disk
          </div>
          <div style={{ marginTop: '6px', fontSize: '22px', fontWeight: 400 }}>Синхронизация источников</div>
        </div>
        <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
          {sync.status === 'running' && (
            <>
              <ActionButton disabled={syncAction === 'pause'} onClick={() => onAction('pause')}>Пауза</ActionButton>
              <ActionButton disabled={syncAction === 'cancel'} onClick={() => onAction('cancel')}>Остановить</ActionButton>
            </>
          )}
          {sync.status === 'paused' && (
            <ActionButton primary disabled={syncAction === 'resume'} onClick={() => onAction('resume')}>Продолжить</ActionButton>
          )}
          <ActionButton disabled={syncAction === 'restart'} onClick={() => onAction('restart')}>Обновить</ActionButton>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))', gap: '12px', marginTop: '16px' }}>
        {[
          ['Найдено', sync.files_found ?? 0],
          ['Скачано', sync.files_downloaded ?? 0],
          ['Пропущено', sync.files_skipped ?? 0],
          ['Ошибок', sync.files_failed ?? 0],
        ].map(([label, value]) => (
          <div key={label} className="depot-card" style={{ padding: '12px 14px' }}>
            <div style={{ color: 'var(--color-smoke)', fontSize: '12px' }}>{label}</div>
            <div style={{ marginTop: '4px', fontSize: '18px', fontWeight: 400 }}>{value}</div>
          </div>
        ))}
      </div>

      {filesFound > 0 && (
        <div style={{ marginTop: '16px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', marginBottom: '8px', color: 'var(--color-smoke)', fontSize: '12px' }}>
            <span>Прогресс</span>
            <span>{pct}%</span>
          </div>
          <div style={{ height: '8px', borderRadius: 0, background: 'rgba(255,255,255,0.05)', overflow: 'hidden' }}>
            <div style={{ width: `${pct}%`, height: '100%', background: 'linear-gradient(90deg, #3b82f6, #60a5fa)' }} />
          </div>
        </div>
      )}

      {sync.last_error && <div style={{ marginTop: '12px', color: '#ef4444', fontSize: '13px' }}>{sync.last_error}</div>}
    </div>
  )
}

export function DocumentsTab() {
  const inputRef = useRef<HTMLInputElement>(null)
  const controllersRef = useRef<Record<string, AbortController>>({})
  const tasksRef = useRef<UploadTask[]>([])
  const [tasks, setTasks] = useState<UploadTask[]>([])
  const [error, setError] = useState<string | null>(null)
  const [docActionKey, setDocActionKey] = useState<string | null>(null)
  const [syncAction, setSyncAction] = useState<string | null>(null)
  const [dragOver, setDragOver] = useState(false)
  const [urlInput, setUrlInput] = useState('')
  const [urlLoading, setUrlLoading] = useState(false)
  const [urlError, setUrlError] = useState<string | null>(null)
  const [urlSuccess, setUrlSuccess] = useState<string | null>(null)
  const [selectedDocId, setSelectedDocId] = useState<string | null>(null)

  const { data: health } = useSWR<Health>('/api/health', fetcher)
  const neo4jReady = Boolean(health?.neo4j)

  const { data: sync, mutate: mutateSync } = useSWR<SyncStatus>(neo4jReady ? '/api/sync/status' : null, fetcher, { refreshInterval: 5000 })
  const { data: docs, mutate } = useSWR<DocumentItem[]>(neo4jReady ? '/api/documents' : null, fetcher, { refreshInterval: 4000 })

  function syncTasks(next: UploadTask[]) {
    tasksRef.current = next
    setTasks(next)
  }

  function patchTask(id: string, patch: Partial<UploadTask>) {
    syncTasks(tasksRef.current.map((task) => (task.id === id ? { ...task, ...patch } : task)))
  }

  function removeTask(id: string) {
    delete controllersRef.current[id]
    syncTasks(tasksRef.current.filter((task) => task.id !== id))
  }

  async function startTask(id: string) {
    const task = tasksRef.current.find((item) => item.id === id)
    if (!task) return
    const controller = new AbortController()
    controllersRef.current[id] = controller
    patchTask(id, { status: 'uploading', error: null })
    setError(null)
    try {
      const uploaded = await uploadFile(task.file, controller.signal)
      delete controllersRef.current[id]
      patchTask(id, { status: 'processing', remoteId: uploaded.id, error: null })
      mutate()
    } catch (err) {
      delete controllersRef.current[id]
      if (err instanceof DOMException && err.name === 'AbortError') {
        patchTask(id, { status: 'stopped', error: null })
        return
      }
      const message = err instanceof Error ? err.message : 'Upload error'
      patchTask(id, { status: 'failed', error: message })
      setError(message)
    }
  }

  function stopTask(id: string) {
    controllersRef.current[id]?.abort()
  }

  function addFiles(files: FileList | null) {
    if (!files?.length) return
    const created = Array.from(files).map((file) => ({
      id: `${file.name}-${file.size}-${crypto.randomUUID()}`,
      file,
      name: file.name,
      size: file.size,
      status: 'queued' as const,
      error: null,
    }))
    syncTasks([...created, ...tasksRef.current])
    created.forEach((task) => void startTask(task.id))
    if (inputRef.current) inputRef.current.value = ''
  }

  async function handleDocumentAction(id: string, action: 'pause' | 'resume' | 'cancel' | 'restart') {
    setDocActionKey(`${id}:${action}`)
    setError(null)
    try {
      await controlDocument(id, action)
      mutate()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Document control error')
    } finally {
      setDocActionKey(null)
    }
  }

  async function handleSyncAction(action: 'pause' | 'resume' | 'cancel' | 'restart') {
    setSyncAction(action)
    setError(null)
    try {
      const next = await controlSync(action)
      mutateSync(next, false)
      mutate()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Sync control error')
    } finally {
      setSyncAction(null)
    }
  }

  const handleUrlImport = useCallback(async () => {
    const url = urlInput.trim()
    if (!url) return
    setUrlLoading(true)
    setUrlError(null)
    setUrlSuccess(null)
    try {
      const result = await importUrl(url)
      setUrlSuccess(`Документ "${result.name}" добавлен в очередь (${result.chunks} chunks)`)
      setUrlInput('')
      mutate()
    } catch (err) {
      setUrlError(err instanceof Error ? err.message : 'Ошибка импорта URL')
    } finally {
      setUrlLoading(false)
    }
  }, [urlInput, mutate])

  const metrics = useMemo(() => {
    const items = docs || []
    return {
      total: items.length,
      ready: items.filter((item) => item.status === 'completed').length,
      processing: items.filter((item) => item.status === 'processing').length,
      chunks: items.reduce((sum, item) => sum + (item.chunks || 0), 0),
    }
  }, [docs])

  return (
    <div>
      <div style={{ display: 'inline-flex', border: '1px solid var(--color-graphite)', marginBottom: '32px', flexWrap: 'wrap' }}>
        <button className="toolbar-btn" onClick={() => neo4jReady && inputRef.current?.click()} style={{ color: 'var(--color-chalk)' }}>
          <FileUp size={14} />
          Загрузить файлы
        </button>
        <div style={{ width: '1px', background: 'var(--color-graphite)' }} />
        <button className="toolbar-btn" onClick={() => sync?.enabled && void handleSyncAction('restart')}>
          <Cloud size={14} />
          Синхронизировать Яндекс Диск
        </button>
        <div style={{ width: '1px', background: 'var(--color-graphite)' }} />
        <button className="toolbar-btn" onClick={() => docs?.[0] && void handleDocumentAction(docs[0].id, 'restart')}>
          <RefreshCw size={14} />
          Перестроить граф
        </button>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '14px', marginBottom: '18px' }}>
        <MetricCard icon={<Files size={14} />} label="Документы" value={metrics.total} />
        <MetricCard icon={<ScanSearch size={14} />} label="Готово" value={metrics.ready} />
        <MetricCard icon={<RefreshCw size={14} />} label="В обработке" value={metrics.processing} />
        <MetricCard icon={<Database size={14} />} label="Chunks" value={metrics.chunks} />
      </div>

      <div className="docs-split" style={{ marginBottom: '18px' }}>
        <section className="depot-card" style={{ padding: '22px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: '16px', alignItems: 'center', marginBottom: '18px', flexWrap: 'wrap' }}>
            <div>
              <div style={{ color: 'var(--color-smoke)', fontSize: '12px', fontWeight: 400, letterSpacing: '0.08em', textTransform: 'uppercase' }}>
                Upload
              </div>
              <div style={{ marginTop: '6px', fontSize: '24px', fontWeight: 760 }}>Добавление источников</div>
            </div>
            <div style={{ color: 'var(--color-smoke)', fontSize: '13px' }}>PDF, DOCX, TXT, MD, CSV</div>
          </div>

          <input
            ref={inputRef}
            type="file"
            multiple
            accept=".pdf,.docx,.txt,.md,.csv"
            style={{ display: 'none' }}
            onChange={(event) => addFiles(event.target.files)}
            aria-label="Select files to upload"
          />

          <div
            onClick={() => neo4jReady && inputRef.current?.click()}
            onDragOver={(event) => { event.preventDefault(); setDragOver(true) }}
            onDragLeave={() => setDragOver(false)}
            onDrop={(event) => {
              event.preventDefault()
              setDragOver(false)
              if (neo4jReady) addFiles(event.dataTransfer.files)
            }}
            style={{
              padding: '42px 24px',
              borderRadius: 0,
              border: `1px dashed ${dragOver ? '#60a5fa' : 'rgba(138, 151, 170, 0.35)'}`,
              background: dragOver ? 'rgba(59,130,246,0.06)' : 'rgba(255,255,255,0.02)',
              cursor: neo4jReady ? 'pointer' : 'not-allowed',
              opacity: neo4jReady ? 1 : 0.55,
            }}
          >
            <div style={{ width: '58px', height: '58px', borderRadius: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(59,130,246,0.12)', border: '1px solid rgba(59,130,246,0.18)', margin: '0 auto 14px' }}>
              <FileUp size={26} color="var(--color-compass-gold)" />
            </div>
            <div style={{ textAlign: 'center', fontSize: '18px', fontWeight: 400 }}>Перетащите файлы сюда</div>
            <div style={{ textAlign: 'center', color: 'var(--color-smoke)', marginTop: '6px' }}>
              или нажмите, чтобы выбрать документы для индексации
            </div>
            {!neo4jReady && <div style={{ textAlign: 'center', color: '#ef4444', marginTop: '10px' }}>Neo4j недоступен</div>}
          </div>

          <div style={{ marginTop: '18px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '10px' }}>
              <Link size={14} color="var(--color-compass-gold)" />
              <span style={{ fontSize: '14px', fontWeight: 400 }}>Импорт по ссылке</span>
              <span style={{ fontSize: '12px', color: 'var(--color-smoke)' }}>
                ResearchGate, eLibrary, Springer, MDPI, CyberLeninka, Wiley, ScienceDirect, Sci-Hub, Google Patents
              </span>
            </div>
            <div style={{ display: 'flex', gap: '10px' }}>
              <input
                type="url"
                value={urlInput}
                onChange={(e) => { setUrlInput(e.target.value); setUrlError(null); setUrlSuccess(null) }}
                onKeyDown={(e) => { if (e.key === 'Enter') handleUrlImport() }}
                placeholder="https://www.sciencedirect.com/science/article/..."
                disabled={!neo4jReady || urlLoading}
                style={{
                  flex: 1,
                  padding: '12px 16px',
                  borderRadius: 0,
                  border: '1px solid rgba(138, 151, 170, 0.25)',
                  background: 'rgba(255,255,255,0.03)',
                  color: 'var(--color-chalk)',
                  fontSize: '14px',
                  outline: 'none',
                  opacity: neo4jReady ? 1 : 0.55,
                }}
              />
              <button
                type="button"
                className="btn-primary"
                onClick={handleUrlImport}
                disabled={!neo4jReady || urlLoading || !urlInput.trim()}
                style={{ padding: '12px 20px', whiteSpace: 'nowrap', opacity: neo4jReady ? 1 : 0.55 }}
              >
                {urlLoading ? 'Загрузка...' : 'Импортировать'}
              </button>
            </div>
            {urlError && <div style={{ marginTop: '8px', color: '#ef4444', fontSize: '13px' }}>{urlError}</div>}
            {urlSuccess && <div style={{ marginTop: '8px', color: '#98ff38', fontSize: '13px' }}>{urlSuccess}</div>}
          </div>

          {error && <div style={{ marginTop: '14px', color: '#ef4444', fontSize: '13px' }}>{error}</div>}

          {tasks.length > 0 && (
            <div style={{ marginTop: '16px', display: 'flex', flexDirection: 'column', gap: '10px' }}>
              {tasks.map((task) => (
                <div key={task.id} className="depot-card" style={{ padding: '14px', display: 'flex', justifyContent: 'space-between', gap: '12px', flexWrap: 'wrap', alignItems: 'center' }}>
                  <div>
                    <div style={{ fontWeight: 400 }}>{task.name}</div>
                    <div style={{ color: 'var(--color-smoke)', fontSize: '12px', marginTop: '4px' }}>
                      {formatBytes(task.size)} · {TASK_LABELS[task.status]}
                    </div>
                    {task.error && <div style={{ color: '#ef4444', fontSize: '12px', marginTop: '4px' }}>{task.error}</div>}
                  </div>
                  <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                    {task.status === 'uploading' && <ActionButton onClick={() => stopTask(task.id)}>Стоп</ActionButton>}
                    {task.status !== 'uploading' && task.status !== 'processing' && (
                      <ActionButton primary onClick={() => void startTask(task.id)}>
                        {task.status === 'queued' ? 'Старт' : 'Повторить'}
                      </ActionButton>
                    )}
                    {task.status !== 'uploading' && <ActionButton onClick={() => removeTask(task.id)}>Убрать</ActionButton>}
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>

        <section style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>
          <div className="depot-card" style={{ padding: '20px' }}>
            <div style={{ color: 'var(--color-smoke)', fontSize: '12px', fontWeight: 400, letterSpacing: '0.08em', textTransform: 'uppercase' }}>
              Pipeline
            </div>
            <div style={{ marginTop: '12px', display: 'grid', gap: '10px' }}>
              {[
                'Загрузка и нормализация файлов',
                'Разбиение на chunks и извлечение сущностей',
                'Построение фактов и обновление графа Neo4j',
              ].map((step, index) => (
                <div key={step} className="depot-card" style={{ padding: '12px 14px', display: 'flex', gap: '12px', alignItems: 'center' }}>
                  <span style={{ width: '24px', height: '24px', borderRadius: 0, border: '1px solid var(--color-graphite)', background: 'transparent', color: 'var(--color-smoke)', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', fontSize: '12px', fontWeight: 400 }}>
                    {index + 1}
                  </span>
                  <span style={{ fontSize: '14px', fontWeight: 400 }}>{step}</span>
                </div>
              ))}
            </div>
          </div>

          {sync?.enabled && <SyncPanel sync={sync} syncAction={syncAction} onAction={handleSyncAction} />}
        </section>
      </div>

      <section className="depot-card" style={{ overflow: 'hidden' }}>
        <div style={{ padding: '20px 22px', borderBottom: '1px solid rgba(37, 48, 68, 0.9)', display: 'flex', justifyContent: 'space-between', gap: '12px', alignItems: 'center', flexWrap: 'wrap' }}>
          <div>
            <div style={{ color: 'var(--color-smoke)', fontSize: '12px', fontWeight: 400, letterSpacing: '0.08em', textTransform: 'uppercase' }}>
              Library
            </div>
            <div style={{ marginTop: '6px', fontSize: '24px', fontWeight: 760 }}>Каталог документов</div>
          </div>
          <div style={{ color: 'var(--color-smoke)', fontSize: '13px' }}>{docs?.length || 0} файлов</div>
        </div>

        {!docs?.length ? (
          <div style={{ padding: '44px 22px', color: 'var(--color-smoke)' }}>
            {neo4jReady ? 'Загрузите первый документ, чтобы увидеть его здесь.' : 'Подключите Neo4j, чтобы увидеть документы.'}
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: '1060px' }}>
              <thead>
                <tr style={{ background: 'rgba(255,255,255,0.02)' }}>
                  {['файл', 'тип', 'размер', 'чанки', 'источник', 'автор', 'загружено', 'статус', 'действия'].map((column) => (
                    <th key={column} style={{ textAlign: 'left', padding: '14px 16px', color: 'var(--color-smoke)', fontSize: '11px', fontWeight: 400, textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                      {column}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {docs.map((doc) => {
                  const ext = doc.name.split('.').pop()?.toUpperCase() || 'FILE'
                  const isSelected = selectedDocId === doc.id
                  return (
                    <tr
                      key={doc.id}
                      onClick={() => setSelectedDocId(isSelected ? null : doc.id)}
                      style={{
                        borderTop: '1px solid var(--color-graphite)',
                        cursor: 'pointer',
                        background: isSelected ? 'rgba(59,130,246,0.06)' : 'transparent',
                        transition: 'background 0.1s',
                      }}
                      onMouseEnter={(e) => { if (!isSelected) e.currentTarget.style.background = 'rgba(255,255,255,0.02)' }}
                      onMouseLeave={(e) => { if (!isSelected) e.currentTarget.style.background = 'transparent' }}
                    >
                      <td style={{ padding: '14px 16px' }}>
                        <div style={{ fontWeight: 400, fontSize: '13px' }}>{doc.name}</div>
                        {doc.error && <div style={{ marginTop: '4px', color: '#ef4444', fontSize: '11px' }}>{doc.error}</div>}
                      </td>
                      <td style={{ padding: '14px 16px', color: 'var(--color-smoke)', fontSize: '13px' }}>{ext}</td>
                      <td style={{ padding: '14px 16px', color: 'var(--color-smoke)', fontSize: '13px' }}>{formatBytes(doc.size)}</td>
                      <td style={{ padding: '14px 16px' }}>
                        <div style={{ fontWeight: 400, fontSize: '13px' }}>{doc.chunks_done}/{doc.chunks_total}</div>
                        <div style={{ marginTop: '6px', height: '4px', borderRadius: 0, background: 'rgba(255,255,255,0.05)', overflow: 'hidden', maxWidth: '120px' }}>
                          <div style={{ width: `${doc.chunks_total > 0 ? Math.round((doc.chunks_done / doc.chunks_total) * 100) : 0}%`, height: '100%', background: 'linear-gradient(90deg, #3b82f6, #60a5fa)' }} />
                        </div>
                      </td>
                      <td style={{ padding: '14px 16px', color: 'var(--color-smoke)', fontSize: '13px' }}>{doc.source_provider || 'manual'}</td>
                      <td style={{ padding: '14px 16px', color: 'var(--color-smoke)', fontSize: '13px' }}>{doc.uploaded_by || '—'}</td>
                      <td style={{ padding: '14px 16px', color: 'var(--color-smoke)', fontSize: '12px' }}>{formatTs(doc.uploaded_at)}</td>
                      <td style={{ padding: '14px 16px' }}><StatusBadge status={doc.status} /></td>
                      <td style={{ padding: '14px 16px' }} onClick={(e) => e.stopPropagation()}>
                        <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                          {doc.status === 'processing' && (
                            <>
                              <ActionButton disabled={docActionKey === `${doc.id}:pause`} onClick={() => void handleDocumentAction(doc.id, 'pause')}>Пауза</ActionButton>
                              <ActionButton disabled={docActionKey === `${doc.id}:cancel`} onClick={() => void handleDocumentAction(doc.id, 'cancel')}>Стоп</ActionButton>
                            </>
                          )}
                          {doc.status === 'paused' && (
                            <>
                              <ActionButton primary disabled={docActionKey === `${doc.id}:resume`} onClick={() => void handleDocumentAction(doc.id, 'resume')}>Продолжить</ActionButton>
                              <ActionButton disabled={docActionKey === `${doc.id}:restart`} onClick={() => void handleDocumentAction(doc.id, 'restart')}>Перезапуск</ActionButton>
                            </>
                          )}
                          {(doc.status === 'failed' || doc.status === 'canceled' || doc.status === 'completed') && (
                            <ActionButton disabled={docActionKey === `${doc.id}:restart`} onClick={() => void handleDocumentAction(doc.id, 'restart')}>Переобработать</ActionButton>
                          )}
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {selectedDocId && <DocumentDetailPanel docId={selectedDocId} onClose={() => setSelectedDocId(null)} />}
    </div>
  )
}
