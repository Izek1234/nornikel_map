'use client'

import { useEffect, useRef, useState } from 'react'
import useSWR from 'swr'
import {
  fetcher,
  postJSON,
  deleteJSON,
  geoLabel,
  type ChatMessage,
  type ChatResponse,
  type RetrievalStats,
  type CacheStats,
  type KnowledgeGap,
  type CompareResult,
} from '@/lib/api'
import { CustomSelect } from './custom-select'
import {
  Plus,
  Trash2,
  Edit3,
  Copy,
  Download,
  FileText,
  ChevronRight,
  ChevronDown,
  Info,
  Check,
  Send,
  PanelLeftClose,
  PanelLeftOpen,
  Database,
  Cpu,
  Sliders,
  ExternalLink
} from 'lucide-react'

const SUGGESTIONS = [
  'Технико-экономическое сравнение вариантов подготовки воды (обессоливания) для обогатительных фабрик ГМК при требованиях к воде по сульфатам, хлоридам, кальцию, магнию, натрию 200-300 мг/л и сухом остатке 1000 мг/дм³',
  'Литературный обзор методов очистки шахтных вод горно-рудных предприятий цветной металлургии (отечественная и мировая практика)',
  'Литературный обзор технических решений для циркуляции католита при производстве никелевых катодов методом электроэкстракции и её оптимальной скорости',
  'Обзор технических решений в области электролитического производства никеля, меди, кобальта (подача, циркуляция, вывод электролита и конструкция диафрагменных ячеек)',
  'Литературный обзор источников техногенного гипса и способов его переработки (отечественная и зарубежная практика)',
  'Анализ технологий и примеров закачки шахтных вод горно-рудных предприятий России и мира в глубокие горизонты',
  'Обзор практик использования угля и отходов угольной промышленности для закладки выработанного пространства',
  'Обзор способов удаления SO2 из отходящих газов металлургических предприятий мира',
  'Обзор распределения Au, Ag и МПГ между медным, никелевым штейном и шлаком по зарубежным источникам последних лет',
  'Обзор современных способов переработки свинцово-цинкового сырья в мировой практике',
]

export type ChatSession = {
  id: string
  title: string
  messages: ChatMessage[]
  region: string
  mode: 'rag' | 'rag_cag'
  updatedAt: number
}

// ── Sub-components ─────────────────────────────────────────────

function ModeBadge({ mode, cached }: { mode?: string; cached?: boolean }) {
  const isCache = cached || mode === 'cache'
  const isGraph = mode === 'graph_rag'
  if (!isCache && !isGraph) return null
  const label = isCache ? '⚡ CAG' : '🔗 GraphRAG'
  const color = isCache ? '#f59e0b' : 'var(--color-compass-gold)'

  return (
    <span style={{
      display: 'inline-flex',
      alignItems: 'center',
      gap: '4px',
      padding: '2px 8px',
      borderRadius: 0,
      border: `1px solid ${color}33`,
      background: `${color}11`,
      fontFamily: "var(--font-mono)",
      fontSize: '11px',
      fontWeight: 400,
      color,
      letterSpacing: '0.02em',
    }}>
      {label}
    </span>
  )
}

function RetrievalPanel({ stats }: { stats: RetrievalStats }) {
  const [open, setOpen] = useState(false)

  return (
    <div style={{ marginTop: '12px', border: '1px solid var(--color-graphite)', background: 'rgba(255,255,255,0.01)' }}>
      <button
        type="button"
        onClick={() => setOpen(o => !o)}
        style={{
          width: '100%',
          background: 'none',
          border: 'none',
          padding: '10px 14px',
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
          fontFamily: "var(--font-mono)",
          fontSize: '12px',
          color: 'var(--color-smoke)',
          cursor: 'pointer',
          outline: 'none',
          textAlign: 'left',
        }}
      >
        {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        СТАТИСТИКА ИЗВЛЕЧЕНИЯ (RETRIEVAL STATS)
      </button>
      {open && (
        <div style={{
          padding: '14px',
          borderTop: '1px solid var(--color-graphite)',
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))',
          gap: '12px',
        }}>
          {[
            { label: 'Сущности', val: stats.entities_found },
            { label: 'Факты', val: stats.facts_found },
            { label: 'Чанки', val: stats.chunks_found },
            { label: 'Шаги (Hops)', val: stats.hops },
            { label: 'Интент', val: stats.query_intent || '—' },
            { label: 'Ограничения', val: stats.constraints_detected ?? 0 },
          ].map(item => (
            <div key={item.label} style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
              <span style={{ fontFamily: "var(--font-mono)", fontSize: '10px', color: 'var(--color-smoke)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>{item.label}</span>
              <span style={{ fontFamily: "var(--font-mono)", fontSize: '13px', color: 'var(--color-chalk)', fontWeight: 400 }}>{item.val}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function ConfidenceBar({ value }: { value: number }) {
  const pct = Math.round(value * 100)
  const color = pct >= 80 ? 'var(--color-compass-gold)' : pct >= 60 ? '#f59e0b' : '#ef4444'

  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
      <span style={{ fontSize: '11px', color, fontWeight: 400, fontFamily: "var(--font-mono)" }}>{pct}%</span>
      <span style={{ width: '40px', height: '4px', background: 'var(--color-graphite)', borderRadius: 0, overflow: 'hidden', display: 'inline-block' }}>
        <span style={{ display: 'block', height: '100%', width: `${pct}%`, background: color, transition: 'width 0.3s' }} />
      </span>
    </span>
  )
}

function FactsPanel({ facts }: { facts: ChatMessage['facts'] }) {
  const [open, setOpen] = useState(false)
  if (!facts || facts.length === 0) return null

  return (
    <div style={{ marginTop: '12px', border: '1px solid var(--color-graphite)', background: 'rgba(255,255,255,0.01)' }}>
      <button
        type="button"
        onClick={() => setOpen(o => !o)}
        style={{
          width: '100%',
          background: 'none',
          border: 'none',
          padding: '10px 14px',
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
          fontFamily: "var(--font-mono)",
          fontSize: '12px',
          color: 'var(--color-smoke)',
          cursor: 'pointer',
          outline: 'none',
          textAlign: 'left',
        }}
      >
        {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        ФАКТЫ ИЗ ГРАФА ЗНАНИЙ ({facts.length})
      </button>
      {open && (
        <div style={{ overflowX: 'auto', padding: '14px', borderTop: '1px solid var(--color-graphite)' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px', textAlign: 'left', fontFamily: 'var(--font-mono)' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--color-graphite)' }}>
                <th style={{ padding: '6px 8px', color: 'var(--color-smoke)', fontWeight: 400, textTransform: 'uppercase' }}>Субъект</th>
                <th style={{ padding: '6px 8px', color: 'var(--color-smoke)', fontWeight: 400, textTransform: 'uppercase' }}>Связь (Предикат)</th>
                <th style={{ padding: '6px 8px', color: 'var(--color-smoke)', fontWeight: 400, textTransform: 'uppercase' }}>Значение</th>
                <th style={{ padding: '6px 8px', color: 'var(--color-smoke)', fontWeight: 400, textTransform: 'uppercase' }}>Гео</th>
                <th style={{ padding: '6px 8px', color: 'var(--color-smoke)', fontWeight: 400, textTransform: 'uppercase' }}>Уверенность</th>
              </tr>
            </thead>
            <tbody>
              {facts.map((f, j) => (
                <tr key={j} style={{ borderBottom: '1px solid rgba(255,255,255,0.03)' }}>
                  <td style={{ padding: '8px', color: '#ffffff', fontWeight: 400 }}>{f.subject}</td>
                  <td style={{ padding: '8px', color: 'var(--color-smoke)' }}>{f.predicate}</td>
                  <td style={{ padding: '8px', color: 'var(--color-compass-gold)', fontWeight: 400 }}>{f.value}</td>
                  <td style={{ padding: '8px', color: 'var(--color-smoke)', fontSize: '11px' }}>{geoLabel(f.geography)}</td>
                  <td style={{ padding: '8px' }}><ConfidenceBar value={f.confidence} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

function MarkdownContent({ content }: { content: string }) {
  const lines = content.split('\n')
  let html = ''
  let inList = false
  let listType: 'ul' | 'ol' | null = null
  let inTable = false
  let isHeaderRow = false
  let inParagraph = false

  const closeParagraph = () => {
    if (inParagraph) {
      html += '</p>\n'
      inParagraph = false
    }
  }

  const closeList = () => {
    if (inList) {
      html += listType === 'ul' ? '</ul>\n' : '</ol>\n'
      inList = false
      listType = null
    }
  }

  const closeTable = () => {
    if (inTable) {
      html += '</table></div>\n'
      inTable = false
    }
  }

  const inlineParse = (text: string): string => {
    return text
      .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
      .replace(/\*([^*]+)\*/g, '<em>$1</em>')
      .replace(/`([^`]+)`/g, '<code style="background:rgba(255,255,255,0.07);padding:2px 6px;border-radius:0;font-family:monospace;font-size:13px;color:var(--color-compass-gold)">$1</code>')
      .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" style="color:var(--color-chalk);text-decoration:underline;text-underline-offset:3px">$1</a>')
  }

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]
    const trimmed = line.trim()

    if (!trimmed) {
      closeParagraph()
      closeList()
      closeTable()
      continue
    }

    // Headers
    const h1Match = line.match(/^# (.*)$/)
    const h2Match = line.match(/^## (.*)$/)
    const h3Match = line.match(/^### (.*)$/)

    if (h1Match) {
      closeParagraph()
      closeList()
      closeTable()
      html += `<h2 style="margin:24px 0 12px;color:#ffffff;font-size:19px;font-weight:700">${inlineParse(h1Match[1])}</h2>\n`
      continue
    }
    if (h2Match) {
      closeParagraph()
      closeList()
      closeTable()
      html += `<h3 style="margin:20px 0 10px;color:#ffffff;font-size:17px;font-weight:600">${inlineParse(h2Match[1])}</h3>\n`
      continue
    }
    if (h3Match) {
      closeParagraph()
      closeList()
      closeTable()
      html += `<h4 style="margin:16px 0 8px;color:var(--color-chalk);font-size:15px;font-weight:600">${inlineParse(h3Match[1])}</h4>\n`
      continue
    }

    // Table Row
    const tableMatch = line.match(/^\|(.*)\|$/)
    if (tableMatch) {
      closeParagraph()
      closeList()
      const cells = tableMatch[1].split('|').map(c => c.trim())
      const isSeparator = cells.every(c => /^:-*|-+:*|:-+:*|-+$/.test(c))

      if (isSeparator) {
        continue
      }

      if (!inTable) {
        html += '<div style="overflow-x:auto;margin:14px 0;"><table style="width:100%;border-collapse:collapse;font-family:var(--font-mono);font-size:13px;border:1px solid var(--color-graphite);">\n'
        inTable = true
        isHeaderRow = true
      }

      html += '<tr style="border-bottom:1px solid var(--color-graphite);">'
      for (const cell of cells) {
        const cellContent = inlineParse(cell)
        if (isHeaderRow) {
          html += `<th style="padding:10px 12px;text-align:left;background:var(--color-carbon);color:var(--color-smoke);font-weight:600;border:1px solid var(--color-graphite);">${cellContent}</th>`
        } else {
          html += `<td style="padding:10px 12px;color:var(--color-chalk);border:1px solid var(--color-graphite);">${cellContent}</td>`
        }
      }
      html += '</tr>\n'
      isHeaderRow = false
      continue
    } else {
      closeTable()
    }

    // Unordered List Items
    const ulMatch = line.match(/^[-•*]\s+(.*)$/)
    if (ulMatch) {
      closeParagraph()
      if (listType !== 'ul') {
        closeList()
        html += '<ul style="margin:10px 0;padding-left:20px;list-style-type:disc;">\n'
        inList = true
        listType = 'ul'
      }
      html += `<li style="margin:6px 0;line-height:1.6">${inlineParse(ulMatch[1])}</li>\n`
      continue
    }

    // Ordered List Items
    const olMatch = line.match(/^(\d+)\.\s+(.*)$/)
    if (olMatch) {
      closeParagraph()
      if (listType !== 'ol') {
        closeList()
        html += '<ol style="margin:10px 0;padding-left:20px;list-style-type:decimal;">\n'
        inList = true
        listType = 'ol'
      }
      html += `<li style="margin:6px 0;line-height:1.6">${inlineParse(olMatch[2])}</li>\n`
      continue
    }

    // If we were in a list but this line is not a list item, close the list
    closeList()

    // Regular paragraph text
    if (!inParagraph) {
      html += '<p style="margin:12px 0;line-height:1.7">'
      inParagraph = true
    }
    html += inlineParse(line) + ' '
  }

  closeParagraph()
  closeList()
  closeTable()

  return (
    <div
      style={{
        fontFamily: "var(--font-aeonik)",
        fontSize: '14.5px',
        lineHeight: 1.7,
        color: '#ffffff',
      }}
      dangerouslySetInnerHTML={{ __html: html }}
    />
  )
}

function KnowledgeGapsPanel() {
  const { data, error, isLoading } = useSWR<{ gaps: KnowledgeGap[] }>('/api/gaps', fetcher)
  const [open, setOpen] = useState(true)

  if (isLoading || error || !data?.gaps?.length) return null

  const severityColor = (s: string) => s === 'high' ? '#ef4444' : s === 'medium' ? '#f59e0b' : 'var(--color-smoke)'

  return (
    <div style={{
      borderRadius: 0,
      border: '1px solid rgba(245, 158, 11, 0.25)',
      background: 'rgba(245, 158, 11, 0.02)',
      marginBottom: '16px'
    }}>
      <button
        type="button"
        onClick={() => setOpen(o => !o)}
        style={{
          width: '100%',
          background: 'none',
          border: 'none',
          padding: '10px 12px',
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          fontFamily: "var(--font-mono)",
          fontSize: '12px',
          color: '#f59e0b',
          cursor: 'pointer',
          textAlign: 'left',
          outline: 'none',
        }}
      >
        <Info size={14} />
        <span style={{ fontWeight: 400 }}>ПРОБЕЛЫ ЗНАНИЙ: {data.gaps.length}</span>
        <span style={{ marginLeft: 'auto' }}>{open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}</span>
      </button>
      {open && (
        <div style={{ padding: '0 12px 10px', display: 'flex', flexDirection: 'column', gap: '8px', maxHeight: '250px', overflowY: 'auto' }}>
          {data.gaps.map((g, i) => (
            <div key={i} style={{
              padding: '8px 10px',
              borderRadius: 0,
              border: '1px solid var(--color-graphite)',
              background: 'var(--color-carbon)',
              display: 'flex',
              gap: '8px',
              alignItems: 'flex-start',
            }}>
              <span style={{
                width: '6px',
                height: '6px',
                borderRadius: '50%',
                background: severityColor(g.severity),
                flexShrink: 0,
                marginTop: '5px',
              }} />
              <div>
                <div style={{ fontFamily: "var(--font-aeonik)", fontSize: '12px', color: 'var(--color-chalk)', fontWeight: 400 }}>{g.topic}</div>
                <div style={{ fontFamily: "var(--font-aeonik)", fontSize: '11px', color: 'var(--color-smoke)', marginTop: '2px' }}>{g.description}</div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function ComparePanel({ onComplete }: { onComplete: (result: CompareResult) => void }) {
  const [a, setA] = useState('')
  const [b, setB] = useState('')
  const [aKey, setAKey] = useState('')
  const [bKey, setBKey] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function compare() {
    if (!aKey || !bKey) return setError('Выберите обе сущности из списка')
    if (aKey === bKey) return setError('Выберите разные сущности')
    setLoading(true)
    setError('')
    try {
      const res = await fetch(`/api/compare?a=${encodeURIComponent(aKey)}&b=${encodeURIComponent(bKey)}`)
      const body = await res.json()
      if (!res.ok) throw new Error(body.detail || 'Ошибка сравнения')
      onComplete(body)
    } catch (e) { setError(e instanceof Error ? e.message : 'Ошибка сравнения') }
    finally { setLoading(false) }
  }

  return (
    <div style={{ marginBottom: '16px' }}>
      <div style={{ fontFamily: "var(--font-mono)", fontSize: '11px', color: 'var(--color-smoke)', marginBottom: '8px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
        СРАВНЕНИЕ СУЩНОСТЕЙ
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
        <CompareEntityInput
          value={a}
          onChange={(value) => { setA(value); setAKey('') }}
          onSelect={(item) => { setA(item.name); setAKey(item.key) }}
          placeholder="Объект A..."
        />
        <CompareEntityInput
          value={b}
          onChange={(value) => { setB(value); setBKey('') }}
          onSelect={(item) => { setB(item.name); setBKey(item.key) }}
          placeholder="Объект B..."
        />
        <button
          type="button"
          onClick={compare}
          disabled={loading || !aKey || !bKey}
          className="btn-ghost"
          style={{ padding: '8px 12px', fontSize: '12px', opacity: loading || !a || !b ? 0.5 : 1, width: '100%', justifyContent: 'center', borderRadius: 0 }}
        >
          {loading ? 'AI АНАЛИЗИРУЕТ...' : 'СРАВНИТЬ С AI ->>'}
        </button>
      </div>
      {error && <div style={{ color: '#ef4444', marginTop: 6, fontSize: 11 }}>{error}</div>}
    </div>
  )
}

type CompareSuggestion = { key: string; name: string; type: string; fact_count: number }

function CompareEntityInput({ value, placeholder, onChange, onSelect }: { value: string; placeholder: string; onChange: (v: string) => void; onSelect: (v: CompareSuggestion) => void }) {
  const [items, setItems] = useState<CompareSuggestion[]>([])
  const [open, setOpen] = useState(false)
  useEffect(() => {
    if (!open) return
    const controller = new AbortController()
    const timer = window.setTimeout(() => fetch(`/api/entities/suggest?q=${encodeURIComponent(value)}`, { signal: controller.signal }).then(r => r.json()).then(r => setItems(r.entities || [])).catch(() => {}), 150)
    return () => { clearTimeout(timer); controller.abort() }
  }, [value, open])
  return <div style={{ position: 'relative' }}>
    <input value={value} placeholder={placeholder} autoComplete="off" onFocus={() => setOpen(true)} onBlur={() => setTimeout(() => setOpen(false), 120)} onChange={e => { onChange(e.target.value); setOpen(true) }} style={{ width: '100%', padding: '8px 10px', background: 'var(--color-carbon)', border: '1px solid var(--color-graphite)', color: 'var(--color-chalk)', fontFamily: 'var(--font-mono)', fontSize: 12, outline: 'none' }} />
    {open && items.length > 0 && <div style={{ position: 'absolute', zIndex: 20, top: '100%', left: 0, right: 0, maxHeight: 190, overflowY: 'auto', background: 'var(--color-carbon)', border: '1px solid var(--color-graphite)' }}>
      {items.map(item => <button key={item.key} type="button" onMouseDown={e => e.preventDefault()} onClick={() => { onSelect(item); setOpen(false) }} style={{ width: '100%', display: 'flex', justifyContent: 'space-between', padding: '8px 10px', background: 'transparent', border: 0, borderBottom: '1px solid var(--color-graphite)', color: 'var(--color-chalk)', cursor: 'pointer', fontSize: 11 }}><span>{item.name}</span><span style={{ color: 'var(--color-smoke)' }}>{item.type} · {item.fact_count}</span></button>)}
    </div>}
  </div>
}

function CacheStatsBar({ onClearCache }: { onClearCache: () => void }) {
  const { data, mutate } = useSWR<CacheStats>('/api/chat/stats', fetcher, { refreshInterval: 30000 })
  if (!data) return null

  async function handleClear() {
    try {
      await deleteJSON('/api/cache')
      mutate()
    } catch {}
    onClearCache()
  }

  return (
    <div style={{
      padding: '10px 12px',
      background: 'var(--color-carbon)',
      borderRadius: 0,
      border: '1px solid var(--color-graphite)',
      display: 'flex',
      flexDirection: 'column',
      gap: '6px',
      fontFamily: "var(--font-mono)",
      fontSize: '11px',
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--color-smoke)' }}>
        <span>КЭШ CAG</span>
        <button
          type="button"
          onClick={handleClear}
          style={{ background: 'none', border: 'none', color: '#ef4444', cursor: 'pointer', fontSize: '11px', padding: 0 }}
        >
          ОЧИСТИТЬ
        </button>
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--color-chalk)' }}>
        <span>Записей: {data.total_entries}</span>
        <span style={{ color: data.hit_rate > 0.5 ? 'var(--color-compass-gold)' : 'var(--color-smoke)' }}>
          Hit Rate: {Math.round((data.hit_rate || 0) * 100)}%
        </span>
      </div>
    </div>
  )
}

// ── Main component ──────────────────────────────────────────────

export function ChatTab() {
  const [sessions, setSessions] = useState<ChatSession[]>([])
  const [activeSessionId, setActiveSessionId] = useState<string>('')
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [sidebarTab, setSidebarTab] = useState<'history' | 'tools'>('history')
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editTitle, setEditTitle] = useState('')
  const [copiedId, setCopiedId] = useState<string | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  // Load from local storage on mount
  useEffect(() => {
    const saved = localStorage.getItem('nornikel_chat_sessions')
    if (saved) {
      try {
        const parsed = JSON.parse(saved)
        if (parsed && parsed.length > 0) {
          setSessions(parsed)
          setActiveSessionId(parsed[0].id)
          return
        }
      } catch (_e) {}
    }
    const defaultSession: ChatSession = { id: `sess-${Date.now()}`, title: 'Новый диалог', messages: [], updatedAt: Date.now(), region: 'world', mode: 'rag' }
    setSessions([defaultSession])
    setActiveSessionId(defaultSession.id)
  }, [])

  // Save to local storage
  useEffect(() => {
    if (sessions.length > 0) {
      localStorage.setItem('nornikel_chat_sessions', JSON.stringify(sessions))
    }
  }, [sessions])

  const activeSession = sessions.find(s => s.id === activeSessionId) || sessions[0]
  const messages = activeSession?.messages || []

  function updateSession(id: string, updates: Partial<ChatSession>) {
    setSessions((prev) => prev.map((session) => (session.id === id ? { ...session, ...updates } : session)))
  }

  function addComparisonToChat(result: CompareResult) {
    if (!activeSession) return
    const now = Date.now()
    const question = `Сравни ${result.entity_a.name} и ${result.entity_b.name}`
    const matrix = result.rows.length
      ? result.rows.map(row => `- **${row.parameter}:** ${result.entity_a.name} — ${row.value_a}; ${result.entity_b.name} — ${row.value_b}`).join('\n')
      : 'Нет параметров для сопоставления.'
    const content = [
      `## Сравнение: ${result.entity_a.name} и ${result.entity_b.name}`,
      '',
      result.analysis || result.analysis_error || 'AI-анализ недоступен.',
      '',
      `**Фактов:** ${result.stats.facts_a} / ${result.stats.facts_b}. **Общих параметров:** ${result.stats.common}.`,
      '',
      '### Матрица сравнения',
      matrix,
    ].join('\n')
    const userMsg: ChatMessage = { id: `compare-user-${now}`, role: 'user', content: question, created_at: now }
    const assistantMsg: ChatMessage = { id: `compare-ai-${now}`, role: 'assistant', content, created_at: now + 1, mode: 'graph_rag' }
    setSessions(prev => prev.map(session => session.id === activeSession.id ? {
      ...session,
      title: session.messages.length ? session.title : `Сравнение: ${result.entity_a.name}`,
      messages: [...session.messages, userMsg, assistantMsg],
      updatedAt: now,
    } : session))
    setSidebarTab('history')
    setTimeout(() => bottomRef.current?.scrollIntoView({ behavior: 'smooth' }), 50)
  }

  async function send(question: string) {
    const q = question.trim()
    if (!q || loading || !activeSession) return
    setInput('')

    const userMsg: ChatMessage = { id: `tmp-user-${Date.now()}`, role: 'user', content: q, created_at: Date.now() }
    const updatedMessages = [...messages, userMsg]
    const title = messages.length === 0 ? (q.length > 28 ? q.substring(0, 28) + '…' : q) : activeSession.title

    updateSession(activeSession.id, { messages: updatedMessages, title, updatedAt: Date.now() })
    setLoading(true)

    // Adjust textarea height back to normal
    if (inputRef.current) {
      inputRef.current.style.height = 'auto'
    }

    try {
      const response = await postJSON<ChatResponse>('/api/chat', {
        question: q,
        region: activeSession.region,
        messages: activeSession.messages.slice(-6).map(m => ({ role: m.role, content: m.content })),
      })
      const asstMsg: ChatMessage = {
        id: `msg-${Date.now()}`,
        role: 'assistant',
        content: response.answer || '',
        sources: response.sources,
        facts: response.facts,
        cached: response.cached,
        mode: response.mode,
        retrieval_stats: response.retrieval_stats,
        created_at: Date.now(),
      }
      updateSession(activeSession.id, { messages: [...updatedMessages, asstMsg], updatedAt: Date.now() })
    } catch (e) {
      updateSession(activeSession.id, {
        messages: [...updatedMessages, {
          id: `tmp-err-${Date.now()}`, role: 'assistant',
          content: e instanceof Error ? e.message : 'Ошибка запроса', error: true, created_at: Date.now(),
        }],
        updatedAt: Date.now(),
      })
    } finally {
      setLoading(false)
      setTimeout(() => bottomRef.current?.scrollIntoView({ behavior: 'smooth' }), 50)
    }
  }

  function createNewChat() {
    const newSession: ChatSession = { id: `sess-${Date.now()}`, title: 'Новый диалог', messages: [], updatedAt: Date.now(), region: 'world', mode: 'rag' }
    setSessions(prev => [newSession, ...prev])
    setActiveSessionId(newSession.id)
    setTimeout(() => inputRef.current?.focus(), 50)
  }

  function deleteChat(id: string) {
    setSessions(prev => {
      const filtered = prev.filter(s => s.id !== id)
      if (filtered.length === 0) {
        const newSession: ChatSession = { id: `sess-${Date.now()}`, title: 'Новый диалог', messages: [], updatedAt: Date.now(), region: 'world', mode: 'rag' }
        setActiveSessionId(newSession.id)
        return [newSession]
      }
      if (id === activeSessionId) setActiveSessionId(filtered[0].id)
      return filtered
    })
  }

  function exportMarkdown(m: ChatMessage) {
    const facts = m.facts?.map(f => `| ${f.subject} | ${f.predicate} | ${f.value} | ${geoLabel(f.geography)} | ${Math.round(f.confidence * 100)}% |`).join('\n') || ''
    const text = [
      '# Ответ AI Агента · Nornickel Knowledge Map',
      '',
      m.content,
      '',
      '---',
      '',
      '## Извлечённые факты',
      '',
      '| Субъект | Предикат | Значение | Гео | Уверенность |',
      '|---------|----------|----------|-----|-------------|',
      facts,
      '',
      '## Источники',
      '',
      m.sources?.map(s => `- ${s}`).join('\n') || 'Нет источников',
    ].join('\n')
    const blob = new Blob([text], { type: 'text/markdown' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `ai-agent-${Date.now()}.md`
    a.click()
    URL.revokeObjectURL(url)
  }

  function exportPDF(m: ChatMessage) {
    const w = window.open('', '_blank')
    if (!w) return
    const factsHtml = m.facts?.map(f =>
      `<tr><td>${f.subject}</td><td>${f.predicate}</td><td><strong>${f.value}</strong></td><td>${geoLabel(f.geography)}</td><td>${Math.round(f.confidence * 100)}%</td></tr>`
    ).join('') || ''
    w.document.write(`<!DOCTYPE html><html><head><meta charset="utf-8"><title>AI Agent Export</title>
    <style>
      body{font-family:-apple-system,sans-serif;max-width:900px;margin:0 auto;padding:40px;color:#111;line-height:1.6}
      h1{font-size:22px;margin-bottom:4px}h2{font-size:16px;margin:24px 0 8px;color:#333}
      .meta{font-size:12px;color:#666;margin-bottom:24px}
      p{margin:8px 0}strong{font-weight:600}em{font-style:italic}
      table{width:100%;border-collapse:collapse;font-size:13px;margin:8px 0}
      th{background:#f4f4f8;text-align:left;padding:8px;border:1px solid #ddd;font-size:12px;color:#555;text-transform:uppercase}
      td{padding:8px;border:1px solid #eee;vertical-align:top}
      .sources{color:#0066cc;font-size:13px}
      @media print{body{padding:20px}}
    </style></head><body>
    <h1>Ответ AI Агента · Nornickel Knowledge Map</h1>
    <div class="meta">Экспортировано: ${new Date().toLocaleString('ru-RU')}</div>
    <div>${m.content.replace(/\n/g, '<br>')}</div>
    ${factsHtml ? `<h2>Извлечённые факты</h2><table><thead><tr><th>Субъект</th><th>Предикат</th><th>Значение</th><th>Гео</th><th>Уверенность</th></tr></thead><tbody>${factsHtml}</tbody></table>` : ''}
    ${m.sources?.length ? `<h2>Источники</h2><div class="sources">${m.sources.join('<br>')}</div>` : ''}
    </body></html>`)
    w.document.close()
    setTimeout(() => w.print(), 600)
  }

  function copyToClipboard(text: string, msgId: string) {
    navigator.clipboard.writeText(text).then(() => {
      setCopiedId(msgId)
      setTimeout(() => setCopiedId(null), 2000)
    }).catch(() => {})
  }

  const handleInputKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      send(input)
    }
  }

  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value)
    if (inputRef.current) {
      inputRef.current.style.height = 'auto'
      inputRef.current.style.height = `${Math.min(inputRef.current.scrollHeight, 200)}px`
    }
  }

  return (
    <div style={{
      display: 'flex',
      height: '100%',
      background: 'var(--color-obsidian)',
      color: 'var(--color-chalk)',
      position: 'relative',
      overflow: 'hidden',
    }}>
      {/* ── LEFT SIDEBAR (History & Tools) ── */}
      <div style={{
        width: sidebarOpen ? '260px' : '0px',
        flexShrink: 0,
        background: 'var(--color-carbon)',
        borderRight: sidebarOpen ? '1px solid var(--color-graphite)' : 'none',
        display: 'flex',
        flexDirection: 'column',
        position: 'relative',
        transition: 'width 0.3s cubic-bezier(0.16, 1, 0.3, 1)',
        zIndex: 40,
        overflow: 'hidden',
      }}>
        {/* Toggle tabs */}
        <div style={{ display: 'flex', borderBottom: '1px solid var(--color-graphite)', background: 'var(--color-carbon)' }}>
          <button
            type="button"
            onClick={() => setSidebarTab('history')}
            style={{
              flex: 1,
              padding: '12px',
              background: 'none',
              border: 'none',
              borderBottom: `2px solid ${sidebarTab === 'history' ? 'var(--color-chalk)' : 'transparent'}`,
              color: sidebarTab === 'history' ? 'var(--color-chalk)' : 'var(--color-smoke)',
              fontFamily: 'var(--font-mono)',
              fontSize: '12px',
              fontWeight: 400,
              cursor: 'pointer',
              outline: 'none',
              transition: 'all 0.2s',
            }}
          >
            ИСТОРИЯ
          </button>
          <button
            type="button"
            onClick={() => setSidebarTab('tools')}
            style={{
              flex: 1,
              padding: '12px',
              background: 'none',
              border: 'none',
              borderBottom: `2px solid ${sidebarTab === 'tools' ? 'var(--color-chalk)' : 'transparent'}`,
              color: sidebarTab === 'tools' ? 'var(--color-chalk)' : 'var(--color-smoke)',
              fontFamily: 'var(--font-mono)',
              fontSize: '12px',
              fontWeight: 400,
              cursor: 'pointer',
              outline: 'none',
              transition: 'all 0.2s',
            }}
          >
            ИНСТРУМЕНТЫ
          </button>
        </div>

        {/* Tab contents */}
        {sidebarTab === 'history' ? (
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
            {/* New Chat Button */}
            <div style={{ padding: '16px 14px' }}>
              <button
                type="button"
                onClick={createNewChat}
                style={{
                  width: '100%',
                  padding: '10px 14px',
                  background: 'transparent',
                  border: '1px dashed var(--color-graphite)',
                  borderRadius: 0,
                  color: 'var(--color-chalk)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '8px',
                  fontFamily: 'var(--font-mono)',
                  fontSize: '13px',
                  cursor: 'pointer',
                  transition: 'all 0.2s',
                }}
                onMouseEnter={e => {
                  e.currentTarget.style.borderColor = 'var(--color-compass-gold)'
                  e.currentTarget.style.background = 'rgba(255, 255, 255, 0.02)'
                }}
                onMouseLeave={e => {
                  e.currentTarget.style.borderColor = 'var(--color-graphite)'
                  e.currentTarget.style.background = 'transparent'
                }}
              >
                <Plus size={16} />
                НОВЫЙ ДИАЛОГ
              </button>
            </div>

            {/* List */}
            <div style={{ flex: 1, overflowY: 'auto', padding: '0 14px 16px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
              {sessions.map(s => (
                <div
                  key={s.id}
                  style={{
                    background: s.id === activeSessionId ? 'var(--color-obsidian)' : 'transparent',
                    border: s.id === activeSessionId ? '1px solid var(--color-graphite)' : '1px solid transparent',
                    borderRadius: 0,
                    padding: '8px 10px',
                    color: s.id === activeSessionId ? 'var(--color-chalk)' : 'var(--color-smoke)',
                    transition: 'all 0.15s',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    gap: '8px',
                    cursor: 'default',
                  }}
                  onMouseEnter={e => { if (s.id !== activeSessionId) e.currentTarget.style.color = 'var(--color-chalk)' }}
                  onMouseLeave={e => { if (s.id !== activeSessionId) e.currentTarget.style.color = 'var(--color-smoke)' }}
                >
                  {editingId === s.id ? (
                    <input
                      autoFocus
                      value={editTitle}
                      onChange={e => setEditTitle(e.target.value)}
                      onKeyDown={e => {
                        if (e.key === 'Enter') {
                          if (editTitle.trim()) updateSession(s.id, { title: editTitle.trim() })
                          setEditingId(null)
                        } else if (e.key === 'Escape') {
                          setEditingId(null)
                        }
                      }}
                      onBlur={() => {
                        if (editTitle.trim()) updateSession(s.id, { title: editTitle.trim() })
                        setEditingId(null)
                      }}
                      style={{
                        flex: 1,
                        background: 'var(--color-obsidian)',
                        border: '1px solid var(--color-graphite)',
                        color: 'var(--color-chalk)',
                        padding: '2px 6px',
                        fontFamily: 'var(--font-mono)',
                        fontSize: '13px',
                        borderRadius: 0,
                        outline: 'none',
                      }}
                    />
                  ) : (
                    <button
                      type="button"
                      onClick={() => setActiveSessionId(s.id)}
                      style={{
                        flex: 1,
                        background: 'none',
                        border: 'none',
                        color: 'inherit',
                        textAlign: 'left',
                        cursor: 'pointer',
                        padding: 0,
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                        fontFamily: 'var(--font-aeonik)',
                        fontSize: '13px',
                        outline: 'none',
                      }}
                    >
                      {s.title}
                    </button>
                  )}
                  <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                    <button
                      type="button"
                      onClick={(e) => { e.stopPropagation(); setEditingId(s.id); setEditTitle(s.title); }}
                      style={{ background: 'none', border: 'none', color: 'inherit', cursor: 'pointer', padding: 0, opacity: 0.5, display: 'flex' }}
                      title="Переименовать"
                    >
                      <Edit3 size={12} />
                    </button>
                    <button
                      type="button"
                      onClick={(e) => { e.stopPropagation(); deleteChat(s.id); }}
                      style={{ background: 'none', border: 'none', color: 'inherit', cursor: 'pointer', padding: 0, opacity: 0.5, display: 'flex' }}
                      title="Удалить"
                    >
                      <Trash2 size={12} />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        ) : (
          <div style={{ flex: 1, overflowY: 'auto', padding: '16px 14px' }}>
            <KnowledgeGapsPanel />
            <ComparePanel onComplete={addComparisonToChat} />
            <CacheStatsBar onClearCache={() => {}} />
          </div>
        )}

        {/* Footer info & selectors */}
        <div style={{
          padding: '14px',
          borderTop: '1px solid var(--color-graphite)',
          background: 'var(--color-carbon)',
          display: 'flex',
          flexDirection: 'column',
          gap: '12px'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span style={{ fontSize: '11px', color: 'var(--color-smoke)', fontFamily: "var(--font-mono)" }}>ГЕО-ПОИСК:</span>
            <CustomSelect
              options={[
                { id: 'world', label: 'WORLD' },
                { id: 'RU', label: 'RUSSIA' },
              ]}
              value={activeSession?.region || 'world'}
              onChange={val => updateSession(activeSession?.id || '', { region: val })}
              direction="up"
            />
          </div>

        </div>
      </div>

      {/* ── WORKSPACE ── */}
      <div style={{
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        position: 'relative',
        background: 'var(--color-obsidian)',
      }}>
        {/* Toggle Collapse Sidebar (floating style) */}
        <button
          type="button"
          onClick={() => setSidebarOpen(o => !o)}
          style={{
            position: 'absolute',
            left: '12px',
            top: '12px',
            zIndex: 45,
            width: '32px',
            height: '32px',
            borderRadius: 0,
            background: 'transparent',
            border: '1px solid rgba(255, 255, 255, 0.15)',
            color: 'rgba(255, 255, 255, 0.4)',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            transition: 'all 0.2s ease',
          }}
          onMouseEnter={e => {
            e.currentTarget.style.color = '#ffffff';
            e.currentTarget.style.borderColor = 'rgba(255, 255, 255, 0.4)';
            e.currentTarget.style.background = 'rgba(255, 255, 255, 0.05)';
          }}
          onMouseLeave={e => {
            e.currentTarget.style.color = 'rgba(255, 255, 255, 0.4)';
            e.currentTarget.style.borderColor = 'rgba(255, 255, 255, 0.15)';
            e.currentTarget.style.background = 'transparent';
          }}
        >
          {sidebarOpen ? <PanelLeftClose size={16} /> : <PanelLeftOpen size={16} />}
        </button>



        {/* Messages Feed */}
        <div style={{
          flex: 1,
          overflowY: 'auto',
          scrollBehavior: 'smooth',
          width: '100%',
        }}>
          {messages.length === 0 ? (
            /* EMPTY WELCOME SCREEN */
            <div style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              minHeight: '100%',
              padding: '60px 24px',
              boxSizing: 'border-box',
            }}>
              <div style={{ maxWidth: '1200px', width: '100%', textAlign: 'center' }}>
                <div style={{
                  width: '60px',
                  height: '60px',
                  borderRadius: 0,
                  border: '1px solid var(--color-compass-gold)',
                  background: 'rgba(255, 255, 255, 0.02)',
                  display: 'inline-flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  marginBottom: '24px',
                  color: 'var(--color-compass-gold)'
                }}>
                  <Cpu size={28} />
                </div>
                <h1 style={{
                  fontFamily: 'var(--font-mono)',
                  fontSize: '26px',
                  fontWeight: 400,
                  color: 'var(--color-chalk)',
                  margin: '0 0 12px 0',
                  textTransform: 'uppercase',
                  letterSpacing: '0.02em'
                }}>
                  В чем я могу помочь?
                </h1>
                <p style={{
                  fontFamily: 'var(--font-aeonik)',
                  fontSize: '14px',
                  color: 'var(--color-smoke)',
                  margin: '0 0 48px 0',
                  lineHeight: 1.5
                }}>
                  Интеллектуальный поиск, извлечение фактов и ответы на вопросы по технологическим базам данных Норникеля.
                </p>

                {/* Suggestions Grid */}
                <div style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
                  gap: '12px',
                  textAlign: 'left'
                }}>
                  {SUGGESTIONS.map((s, idx) => (
                    <button
                      key={idx}
                      type="button"
                      onClick={() => send(s)}
                      style={{
                        padding: '16px',
                        background: 'var(--color-carbon)',
                        border: '1px solid var(--color-graphite)',
                        borderRadius: 0,
                        color: 'var(--color-smoke)',
                        textAlign: 'left',
                        fontFamily: 'var(--font-aeonik)',
                        fontSize: '13px',
                        lineHeight: 1.5,
                        cursor: 'pointer',
                        transition: 'all 0.2s cubic-bezier(0.16, 1, 0.3, 1)',
                        display: 'flex',
                        flexDirection: 'column',
                        justifyContent: 'space-between',
                        minHeight: '84px',
                        outline: 'none',
                      }}
                      onMouseEnter={e => {
                        e.currentTarget.style.borderColor = 'var(--color-compass-gold)'
                        e.currentTarget.style.color = 'var(--color-chalk)'
                        e.currentTarget.style.background = 'rgba(255, 255, 255, 0.02)'
                      }}
                      onMouseLeave={e => {
                        e.currentTarget.style.borderColor = 'var(--color-graphite)'
                        e.currentTarget.style.color = 'var(--color-smoke)'
                        e.currentTarget.style.background = 'var(--color-carbon)'
                      }}
                    >
                      <span>{s}</span>
                      <span style={{
                        fontSize: '11px',
                        fontFamily: 'var(--font-mono)',
                        color: 'var(--color-compass-gold)',
                        marginTop: '8px',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '2px',
                        opacity: 0.9
                      }}>
                        Спросить AI Агента -&gt;&gt;
                      </span>
                    </button>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            /* CONVERSATION FEED */
            <div style={{
              maxWidth: '1200px',
              margin: '0 auto',
              padding: '40px 24px 120px',
              display: 'flex',
              flexDirection: 'column',
              gap: '32px',
            }}>
              {messages.map((m, i) => (
                <div
                  key={m.id || i}
                  style={{
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: m.role === 'user' ? 'flex-end' : 'flex-start',
                    width: '100%',
                  }}
                >
                  {m.role === 'user' ? (
                    /* User side bubble */
                    <div style={{
                      background: 'var(--color-carbon)',
                      border: '1px solid var(--color-graphite)',
                      padding: '12px 18px',
                      borderRadius: 0,
                      maxWidth: '85%',
                      fontFamily: "var(--font-aeonik)",
                      fontSize: '14.5px',
                      color: 'var(--color-chalk)',
                      lineHeight: 1.5,
                    }}>
                      {m.content}
                    </div>
                  ) : (
                    /* Assistant side reply */
                    <div style={{
                      width: '100%',
                      display: 'flex',
                      gap: '14px',
                      alignItems: 'flex-start',
                    }}>
                      {/* Icon */}
                      <div style={{
                        width: '28px',
                        height: '28px',
                        borderRadius: 0,
                        background: 'rgba(255, 255, 255, 0.02)',
                        border: '1px solid var(--color-compass-gold)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        fontSize: '11px',
                        fontWeight: 'normal',
                        fontFamily: 'var(--font-mono)',
                        color: 'var(--color-compass-gold)',
                        flexShrink: 0,
                        marginTop: '2px',
                      }}>
                        AI
                      </div>

                      {/* Content panel */}
                      <div style={{ flex: 1, overflow: 'hidden' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                          <span style={{ fontFamily: "var(--font-mono)", fontSize: '12px', color: 'var(--color-chalk)', textTransform: 'uppercase' }}>AI Агент</span>
                          {!m.error && <ModeBadge mode={m.mode} cached={m.cached} />}
                        </div>
                        <div style={{ fontFamily: "var(--font-aeonik)", fontSize: '14.5px', color: '#ececec', lineHeight: 1.6 }}>
                          {m.error ? (
                            <span style={{ color: '#ef4444' }}>{m.content}</span>
                          ) : (
                            <MarkdownContent content={m.content} />
                          )}
                        </div>

                        {/* Extra panels for facts and sources */}
                        {!m.error && (
                          <>
                            {m.facts && m.facts.length > 0 && <FactsPanel facts={m.facts} />}
                            {m.sources && m.sources.length > 0 && (
                              <div style={{ marginTop: '16px', display: 'flex', flexWrap: 'wrap', gap: '8px', alignItems: 'center' }}>
                                <span style={{ fontSize: '11px', fontFamily: 'var(--font-mono)', color: 'var(--color-smoke)', marginRight: '4px' }}>ИСТОЧНИКИ:</span>
                                {m.sources.map((s, idx) => (
                                  <button
                                    key={idx}
                                    type="button"
                                    onClick={() => window.open(`/viewer?name=${encodeURIComponent(s)}`, '_blank')}
                                    style={{
                                      display: 'inline-flex',
                                      alignItems: 'center',
                                      gap: '6px',
                                      padding: '4px 10px',
                                      borderRadius: 0,
                                      background: 'var(--color-carbon)',
                                      border: '1px solid var(--color-graphite)',
                                      color: 'var(--color-chalk)',
                                      fontFamily: 'var(--font-mono)',
                                      fontSize: '11px',
                                      cursor: 'pointer',
                                      transition: 'all 0.15s',
                                    }}
                                    onMouseEnter={e => {
                                      e.currentTarget.style.borderColor = 'var(--color-compass-gold)'
                                      e.currentTarget.style.background = 'rgba(255,255,255,0.05)'
                                    }}
                                    onMouseLeave={e => {
                                      e.currentTarget.style.borderColor = 'var(--color-graphite)'
                                      e.currentTarget.style.background = 'var(--color-carbon)'
                                    }}
                                  >
                                    <FileText size={12} style={{ color: 'var(--color-compass-gold)' }} />
                                    {s}
                                  </button>
                                ))}
                              </div>
                            )}
                          </>
                        )}

                        {/* Actions bar */}
                        {!m.error && (
                          <div style={{ display: 'flex', gap: '14px', marginTop: '16px', borderTop: '1px solid var(--color-graphite)', paddingTop: '10px' }}>
                            <button
                              type="button"
                              onClick={() => copyToClipboard(m.content, m.id || String(i))}
                              style={{ background: 'none', border: 'none', color: 'var(--color-smoke)', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '4px', fontSize: '11px', fontFamily: 'var(--font-mono)', padding: 0 }}
                              title="Копировать"
                            >
                              {copiedId === (m.id || String(i)) ? (
                                <>
                                  <Check size={13} style={{ color: '#98ff38' }} />
                                  <span style={{ color: '#98ff38' }}>СКОПИРОВАНО</span>
                                </>
                              ) : (
                                <>
                                  <Copy size={13} />
                                  <span>КОПИРОВАТЬ</span>
                                </>
                              )}
                            </button>
                            <button
                              type="button"
                              onClick={() => exportMarkdown(m)}
                              style={{ background: 'none', border: 'none', color: 'var(--color-smoke)', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '4px', fontSize: '11px', fontFamily: 'var(--font-mono)', padding: 0 }}
                              title="Экспорт Markdown"
                            >
                              <Download size={13} />
                              <span>MARKDOWN</span>
                            </button>
                            <button
                              type="button"
                              onClick={() => exportPDF(m)}
                              style={{ background: 'none', border: 'none', color: 'var(--color-smoke)', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '4px', fontSize: '11px', fontFamily: 'var(--font-mono)', padding: 0 }}
                              title="Экспорт PDF"
                            >
                              <FileText size={13} />
                              <span>PDF</span>
                            </button>
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              ))}

              {loading && (
                <div style={{ display: 'flex', gap: '14px', alignItems: 'flex-start' }}>
                  <div style={{
                    width: '28px',
                    height: '28px',
                    borderRadius: 0,
                    background: 'rgba(255, 255, 255, 0.02)',
                    border: '1px solid var(--color-compass-gold)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: '11px',
                    fontWeight: 'normal',
                    fontFamily: 'var(--font-mono)',
                    color: 'var(--color-compass-gold)',
                    flexShrink: 0,
                  }}>
                    AI
                  </div>
                  <div style={{ display: 'flex', gap: '6px', height: '28px', alignItems: 'center' }}>
                    {[0, 1, 2].map(dot => (
                      <span
                        key={dot}
                        style={{
                          width: '6px',
                          height: '6px',
                          borderRadius: '50%',
                          background: 'var(--color-smoke)',
                          animation: 'pulse 1.2s infinite ease-in-out',
                          animationDelay: `${dot * 0.2}s`
                        }}
                      />
                    ))}
                  </div>
                </div>
              )}
              <div ref={bottomRef} style={{ height: '20px' }} />
            </div>
          )}
        </div>

        {/* Floating Bottom Input Area */}
        <div style={{
          position: 'absolute',
          bottom: 0,
          left: 0,
          right: 0,
          background: 'linear-gradient(to top, var(--color-obsidian) 70%, transparent 100%)',
          padding: '20px 24px 20px',
          zIndex: 25,
        }}>
          <div style={{ maxWidth: '1200px', margin: '0 auto', position: 'relative' }}>
            <form onSubmit={e => { e.preventDefault(); send(input) }}>
              <div style={{
                display: 'flex',
                alignItems: 'flex-end',
                background: 'var(--color-carbon)',
                border: '1px solid var(--color-graphite)',
                borderRadius: 0,
                padding: '12px 14px',
                boxShadow: 'none',
              }}>
                <textarea
                  ref={inputRef}
                  value={input}
                  onChange={handleInputChange}
                  onKeyDown={handleInputKeyDown}
                  placeholder="Задайте вопрос..."
                  disabled={loading}
                  rows={1}
                  style={{
                    flex: 1,
                    background: 'none',
                    border: 'none',
                    color: 'var(--color-chalk)',
                    fontFamily: "var(--font-aeonik)",
                    fontSize: '14.5px',
                    outline: 'none',
                    resize: 'none',
                    maxHeight: '200px',
                    lineHeight: '22px',
                    padding: '4px 8px',
                    boxSizing: 'border-box',
                  }}
                />
                <button
                  type="submit"
                  disabled={loading || !input.trim()}
                  style={{
                    width: '32px',
                    height: '32px',
                    background: loading || !input.trim() ? 'rgba(255,255,255,0.03)' : 'var(--color-chalk)',
                    border: 'none',
                    borderRadius: 0,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    cursor: loading || !input.trim() ? 'not-allowed' : 'pointer',
                    color: loading || !input.trim() ? 'var(--color-smoke)' : 'var(--color-obsidian)',
                    transition: 'all 0.2s',
                    flexShrink: 0,
                    marginBottom: '2px',
                    outline: 'none',
                  }}
                >
                  <Send size={15} />
                </button>
              </div>
            </form>

          </div>
        </div>
      </div>
    </div>
  )
}
