'use client'

import { type ReactNode, useEffect, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import useSWR from 'swr'
import {
  forceCenter,
  forceCollide,
  forceLink,
  forceManyBody,
  forceSimulation,
  forceX,
  forceY,
  type SimulationLinkDatum,
  type SimulationNodeDatum,
} from 'd3-force'
import {
  ENTITY_TYPE_COLORS,
  ENTITY_TYPE_LABELS,
  fetcher,
  fetchDomains,
  exportJsonLdSubgraph,
  exportJsonLdEntity,
  type Domain,
  type EntityDetails,
  type GraphData,
  type GraphLink,
  type GraphNode,
} from '@/lib/api'
import { CustomSelect } from './custom-select'

type SimNode = SimulationNodeDatum & GraphNode
type SimLink = SimulationLinkDatum<SimNode> & GraphLink
type TransformState = { x: number; y: number; scale: number }

const TYPES = Object.keys(ENTITY_TYPE_LABELS)
const MIN_SCALE = 0.25
const MAX_SCALE = 3.5

// Constant starry background coordinate lists for Obsidian-Space design
const STARS = Array.from({ length: 180 }, (_, i) => {
  const x = (Math.random() - 0.5) * 4500 + 450
  const y = (Math.random() - 0.5) * 3500 + 310
  const r = Math.random() * 1.5 + 0.4
  const opacity = Math.random() * 0.8 + 0.2
  const randColor = Math.random()
  // 10% chance of colored space stars (blue/red), otherwise warm white
  const color = randColor < 0.08 ? '#a5f3fc' : randColor > 0.92 ? '#fecdd3' : '#ffffff'
  const twinkleClass = `star-twinkle-${(i % 3) + 1}`
  return { id: i, x, y, r, opacity, color, twinkleClass }
})

const graphToolbarLabelStyle = {
  fontFamily: "var(--font-helvetica-now-text)",
  fontSize: '12px',
  fontWeight: 400,
  color: '#646e87',
  whiteSpace: 'nowrap' as const,
}

const graphInputStyle = {
  height: '44px',
  padding: '0 14px',
  background: 'var(--control-bg)',
  border: '1px solid var(--control-border)',
  borderRadius: 0,
  color: 'var(--control-text)',
  fontFamily: "var(--font-helvetica-now-text)",
  fontSize: '13px',
  outline: 'none',
}

const graphActionButtonStyle = {
  height: '44px',
  padding: '0 16px',
  borderRadius: 0,
  border: '1px solid var(--control-border)',
  background: 'var(--control-bg)',
  color: 'var(--control-text)',
  fontFamily: "var(--font-helvetica-now-text)",
  fontSize: '13px',
  fontWeight: 400,
  cursor: 'pointer',
}

function parseOptionalNumber(value: string) {
  const normalized = value.trim().replace(',', '.')
  if (!normalized) return null
  const parsed = Number(normalized)
  return Number.isFinite(parsed) ? parsed : null
}

function parseOptionalInteger(value: string) {
  const normalized = value.trim()
  if (!normalized) return null
  const parsed = Number(normalized)
  return Number.isInteger(parsed) ? parsed : null
}

/* Node radius based on connectivity */
function nodeRadius(degree: number): number {
  return 5 + Math.min(Math.sqrt(degree) * 2.2, 14)
}

const LABEL_MAX_CHARS = 21

function wrapNodeLabel(value: string): string[] {
  const words = value.trim().split(/\s+/)
  const lines: string[] = []

  for (const word of words) {
    if (word.length > LABEL_MAX_CHARS) {
      if (lines.length < 2) lines.push(`${word.slice(0, LABEL_MAX_CHARS - 1)}…`)
      break
    }
    const index = Math.max(0, lines.length - 1)
    const candidate = lines.length ? `${lines[index]} ${word}` : word
    if (!lines.length || candidate.length > LABEL_MAX_CHARS) {
      if (lines.length === 2) {
        lines[1] = `${lines[1].slice(0, LABEL_MAX_CHARS - 1).trimEnd()}…`
        break
      }
      lines.push(word)
    } else {
      lines[index] = candidate
    }
  }

  return lines.length ? lines : ['Без названия']
}

export function GraphTab() {
  const [search, setSearch] = useState('')
  const [debounced, setDebounced] = useState('')
  const [typeFilters, setTypeFilters] = useState<Set<string>>(new Set())
  const [selected, setSelected] = useState<string | null>(null)

  const [regionFilter, setRegionFilter] = useState('all')
  const [domainFilter, setDomainFilter] = useState('all')
  const [domains, setDomains] = useState<Domain[]>([])
  const [accThreshold, setAccThreshold] = useState('')
  const [yearFrom, setYearFrom] = useState('')
  const [monthFrom, setMonthFrom] = useState('')
  const [yearTo, setYearTo] = useState('')
  const [monthTo, setMonthTo] = useState('')

  useEffect(() => {
    fetchDomains().then(setDomains).catch(() => {})
  }, [])

  useEffect(() => {
    const timer = setTimeout(() => setDebounced(search), 350)
    return () => clearTimeout(timer)
  }, [search])

  const url = useMemo(() => {
    const params = new URLSearchParams()
    if (debounced.trim()) params.set('search', debounced.trim())
    if (typeFilters.size > 0) params.set('type', Array.from(typeFilters).join(','))
    if (regionFilter !== 'all') params.set('region', regionFilter)
    if (domainFilter !== 'all') params.set('domain', domainFilter)

    const parsedAccThreshold = parseOptionalNumber(accThreshold)
    const parsedYearFrom = parseOptionalInteger(yearFrom)
    const parsedMonthFrom = parseOptionalInteger(monthFrom)
    const parsedYearTo = parseOptionalInteger(yearTo)
    const parsedMonthTo = parseOptionalInteger(monthTo)

    if (parsedAccThreshold !== null) params.set('min_confidence', String(parsedAccThreshold))
    if (parsedYearFrom !== null) params.set('year_from', String(parsedYearFrom))
    if (parsedMonthFrom !== null) params.set('month_from', String(parsedMonthFrom))
    if (parsedYearTo !== null) params.set('year_to', String(parsedYearTo))
    if (parsedMonthTo !== null) params.set('month_to', String(parsedMonthTo))

    const qs = params.toString()
    return qs ? `/api/graph?${qs}` : '/api/graph'
  }, [accThreshold, debounced, domainFilter, monthFrom, monthTo, regionFilter, typeFilters, yearFrom, yearTo])

  const { data, error, isLoading } = useSWR<GraphData>(url, fetcher, { keepPreviousData: true })
  const { data: details, error: detailsError, isLoading: detailsLoading } = useSWR<EntityDetails>(
    selected ? `/api/entity/${encodeURIComponent(selected)}` : null,
    fetcher,
  )

  const [readingDoc, setReadingDoc] = useState<string | null>(null)

  function resetToolbarFilters() {
    setSearch('')
    setDebounced('')
    setRegionFilter('all')
    setDomainFilter('all')
    setAccThreshold('')
    setYearFrom('')
    setMonthFrom('')
    setYearTo('')
    setMonthTo('')
    setTypeFilters(new Set())
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>

      {readingDoc && (
        <DocumentReaderModal
          docName={readingDoc}
          onClose={() => setReadingDoc(null)}
        />
      )}

      {/* ── Controls bar ── */}
      <section className="depot-card frosted-panel" style={{
        flexShrink: 0,
        padding: '18px 22px',
        display: 'flex',
        flexDirection: 'column',
        gap: '18px',
        position: 'relative',
        zIndex: 20,
        borderRadius: 0,
        marginBottom: '18px',
      }}>


        <div style={{ display: 'flex', alignItems: 'center', gap: '14px', flexWrap: 'wrap' }}>
          {/* Search Input (Self-explanatory placeholder, no heavy label) */}
          <div style={{ display: 'flex', alignItems: 'center', position: 'relative' }}>
            <input
              className="control-input"
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Поиск сущностей..."
              aria-label="Search entity"
              style={{ ...graphInputStyle, width: '240px', paddingLeft: '14px' }}
            />
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <span style={graphToolbarLabelStyle}>Регион</span>
            <CustomSelect
              options={[
                { id: 'all', label: 'Любой регион' },
                { id: 'RU', label: 'Россия' },
                { id: 'world', label: 'Мир' },
              ]}
              value={regionFilter}
              onChange={setRegionFilter}
            />
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <span style={graphToolbarLabelStyle}>Домен</span>
            <CustomSelect
              options={[
                { id: 'all', label: 'Все домены' },
                ...domains.map(d => ({ id: d.id, label: d.name_ru })),
              ]}
              value={domainFilter}
              onChange={setDomainFilter}
            />
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <span style={graphToolbarLabelStyle}>Точность</span>
            <input
              className="control-input"
              value={accThreshold}
              onChange={e => {
                const val = e.target.value
                const normalized = val.trim().replace(',', '.')
                if (normalized) {
                  const parsed = Number(normalized)
                  if (Number.isFinite(parsed) && parsed > 1) {
                    setAccThreshold('1')
                    return
                  }
                }
                setAccThreshold(val)
              }}
              placeholder="0.0 - 1.0"
              inputMode="decimal"
              aria-label="Accuracy threshold"
              style={{ ...graphInputStyle, width: '85px', textAlign: 'center' }}
            />
          </div>

          {/* Clean, intuitive unified date range selector */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <span style={graphToolbarLabelStyle}>Период</span>
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
              background: 'var(--control-bg)',
              border: '1px solid var(--control-border)',
              padding: '0 12px',
              height: '44px',
              borderRadius: 0,
              transition: 'border-color 0.2s',
            }}>
              <input
                className="date-mini-input"
                value={monthFrom}
                onChange={e => setMonthFrom(e.target.value)}
                placeholder="ММ"
                maxLength={2}
                inputMode="numeric"
                style={{ background: 'transparent', border: 0, outline: 0, width: '26px', color: 'var(--color-chalk)', fontSize: '13px', textAlign: 'center', padding: 0 }}
              />
              <span style={{ color: 'var(--color-graphite)', fontSize: '12px' }}>/</span>
              <input
                className="date-mini-input"
                value={yearFrom}
                onChange={e => setYearFrom(e.target.value)}
                placeholder="ГГГГ"
                maxLength={4}
                inputMode="numeric"
                style={{ background: 'transparent', border: 0, outline: 0, width: '38px', color: 'var(--color-chalk)', fontSize: '13px', textAlign: 'center', padding: 0 }}
              />
              <span style={{ color: 'var(--color-smoke)', margin: '0 6px', fontSize: '12px' }}>—</span>
              <input
                className="date-mini-input"
                value={monthTo}
                onChange={e => setMonthTo(e.target.value)}
                placeholder="ММ"
                maxLength={2}
                inputMode="numeric"
                style={{ background: 'transparent', border: 0, outline: 0, width: '26px', color: 'var(--color-chalk)', fontSize: '13px', textAlign: 'center', padding: 0 }}
              />
              <span style={{ color: 'var(--color-graphite)', fontSize: '12px' }}>/</span>
              <input
                className="date-mini-input"
                value={yearTo}
                onChange={e => setYearTo(e.target.value)}
                placeholder="ГГГГ"
                maxLength={4}
                inputMode="numeric"
                style={{ background: 'transparent', border: 0, outline: 0, width: '38px', color: 'var(--color-chalk)', fontSize: '13px', textAlign: 'center', padding: 0 }}
              />
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <button
              type="button"
              onClick={() => setDebounced(search.trim())}
              title="Apply filters"
              style={{
                width: '44px',
                height: '44px',
                display: 'grid',
                placeItems: 'center',
                background: 'var(--control-bg)',
                border: '1px solid var(--control-border)',
                color: 'var(--color-smoke)',
                cursor: 'pointer',
                transition: 'all 0.2s',
              }}
              onMouseEnter={e => {
                e.currentTarget.style.borderColor = '#3df2b4'
                e.currentTarget.style.color = '#3df2b4'
                e.currentTarget.style.boxShadow = '0 0 8px rgba(61, 242, 180, 0.2)'
              }}
              onMouseLeave={e => {
                e.currentTarget.style.borderColor = 'var(--control-border)'
                e.currentTarget.style.color = 'var(--color-smoke)'
                e.currentTarget.style.boxShadow = 'none'
              }}
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="20 6 9 17 4 12" />
              </svg>
            </button>

            <button
              type="button"
              onClick={resetToolbarFilters}
              title="Reset filters"
              style={{
                width: '44px',
                height: '44px',
                display: 'grid',
                placeItems: 'center',
                background: 'var(--control-bg)',
                border: '1px solid var(--control-border)',
                color: 'var(--color-smoke)',
                cursor: 'pointer',
                transition: 'all 0.2s',
              }}
              onMouseEnter={e => {
                e.currentTarget.style.borderColor = '#ef4444'
                e.currentTarget.style.color = '#ef4444'
                e.currentTarget.style.boxShadow = '0 0 8px rgba(239, 68, 68, 0.2)'
              }}
              onMouseLeave={e => {
                e.currentTarget.style.borderColor = 'var(--control-border)'
                e.currentTarget.style.color = 'var(--color-smoke)'
                e.currentTarget.style.boxShadow = 'none'
              }}
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" />
                <polyline points="3 3 3 8 8 8" />
              </svg>
            </button>
          </div>

          <div style={{ flex: 1 }} />

          <div className="panel-muted" style={{ display: 'flex', alignItems: 'center', gap: '16px', padding: '10px 16px', borderRadius: 0, height: '44px' }}>
            <span style={{ fontFamily: "var(--font-helvetica-now-text)", fontSize: '12px', color: '#646e87', letterSpacing: '0.05em' }}>
              УЗЛЫ: <span style={{ color: '#ffffff', fontWeight: 400 }}>{data?.nodes.length ?? 0}</span>
            </span>
            <span style={{ width: '1px', height: '12px', background: 'var(--color-graphite)' }} />
            <span style={{ fontFamily: "var(--font-aeonik)", fontSize: '12px', color: 'var(--color-smoke)', letterSpacing: '0.05em' }}>
              СВЯЗИ: <span style={{ color: '#ffffff', fontWeight: 400 }}>{data?.links.length ?? 0}</span>
            </span>
            <span style={{ width: '1px', height: '12px', background: 'var(--color-graphite)' }} />
            <button
              type="button"
              onClick={() => {
                exportJsonLdSubgraph({
                  search: debounced || undefined,
                  type: typeFilters.size > 0 ? Array.from(typeFilters).join(',') : undefined,
                  region: regionFilter !== 'all' ? regionFilter : undefined,
                  domain: domainFilter !== 'all' ? domainFilter : undefined,
                  min_confidence: parseOptionalNumber(accThreshold) ?? undefined,
                  year_from: parseOptionalInteger(yearFrom) ?? undefined,
                  year_to: parseOptionalInteger(yearTo) ?? undefined,
                })
              }}
              style={{
                fontFamily: "var(--font-helvetica-now-text)", fontSize: '12px',
                color: '#646e87', background: 'transparent', border: '1px solid var(--color-graphite)',
                padding: '4px 10px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px',
                transition: 'all 0.2s',
              }}
              onMouseEnter={e => { e.currentTarget.style.borderColor = 'var(--color-chalk)'; e.currentTarget.style.color = '#ffffff' }}
              onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--color-graphite)'; e.currentTarget.style.color = '#646e87' }}
              title="Экспорт текущего подграфа в JSON-LD"
            >
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/>
                <polyline points="7 10 12 15 17 10"/>
                <line x1="12" y1="15" x2="12" y2="3"/>
              </svg>
              JSON-LD
            </button>
          </div>
        </div>

        <div style={{ display: 'flex', gap: '20px', alignItems: 'center' }}>
          <span style={{ fontFamily: "var(--font-helvetica-now-text)", fontSize: '12px', fontWeight: 400, color: '#646e87', textTransform: 'uppercase' }}>Типы</span>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', alignItems: 'center' }} role="group">
            <FilterChip active={typeFilters.size === 0} onClick={() => setTypeFilters(new Set())} color="#ffffff">Все</FilterChip>
            {TYPES.map(type => (
              <FilterChip
                key={type}
                active={typeFilters.has(type)}
                onClick={() => setTypeFilters(prev => {
                  const next = new Set(prev)
                  if (next.has(type)) next.delete(type); else next.add(type)
                  return next
                })}
                color={ENTITY_TYPE_COLORS[type] || 'var(--color-smoke)'}
              >
                {ENTITY_TYPE_LABELS[type]}
              </FilterChip>
            ))}
          </div>
        </div>
      </section>

      {/* ── Main graph area ── */}
      <div 
        className="flex-1 min-h-0 flex flex-col lg:flex-row overflow-hidden gap-[18px]"
        style={{ position: 'relative' }}
      >

        {/* Canvas */}
        <section 
          className="relative min-h-[50vh] lg:min-h-0 flex-1 overflow-hidden depot-card frosted-panel"
        >
          {error ? (
            <StateMessage icon="⚠">Ошибка Neo4j — проверьте подключение к базе данных.</StateMessage>
          ) : !data || data.nodes.length === 0 ? (
            <StateMessage icon="◎">
              {isLoading ? 'Загрузка графа...' : 'Граф пуст. Загрузите документы.'}
            </StateMessage>
          ) : (
            <GraphViewport data={data} selected={selected} onSelect={setSelected} />
          )}
        </section>

        {/* Side panel */}
        {selected && (
          <aside 
            className="depot-card frosted-panel portal-panel-animated flex flex-col overflow-y-auto"
            style={{
              position: 'absolute',
              top: 0,
              right: 0,
              bottom: 0,
              width: '360px',
              height: '100%',
              zIndex: 30,
              padding: '24px',
              gap: '0',
            }}
          >
            <div style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              marginBottom: '24px'
            }}>
              <div style={{
                fontFamily: "var(--font-aeonik)", fontWeight: 400,
                fontSize: '12px', letterSpacing: '0.1em', textTransform: 'uppercase',
                color: 'var(--color-smoke)', display: 'flex', alignItems: 'center', gap: '8px'
              }}>
                Детали узла
              </div>
              <button
                type="button"
                onClick={() => setSelected(null)}
                style={{
                  background: 'transparent',
                  border: 'none',
                  color: 'var(--color-smoke)',
                  cursor: 'pointer',
                  padding: '4px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  transition: 'color 0.2s',
                }}
                onMouseEnter={e => e.currentTarget.style.color = '#ffffff'}
                onMouseLeave={e => e.currentTarget.style.color = 'var(--color-smoke)'}
                title="Закрыть панель"
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="18" y1="6" x2="6" y2="18"></line>
                  <line x1="6" y1="6" x2="18" y2="18"></line>
                </svg>
              </button>
            </div>

            {detailsError ? (
              <EmptyPane icon="⚠" color="#ef4444">Не удалось загрузить детали. Выберите другой узел.</EmptyPane>
            ) : detailsLoading ? (
              <EmptyPane icon="◎" pulse>Загрузка...</EmptyPane>
            ) : !details ? (
              <EmptyPane icon="◈">Выберите узел для просмотра фактов и источников.</EmptyPane>
            ) : (
              <EntityPanel entityKey={selected!} details={details} onDocSelect={(docName) => window.open(`/viewer?name=${encodeURIComponent(docName)}`, '_blank')} />
            )}
          </aside>
        )}
      </div>
    </div>
  )
}

/* ── Graph Viewport ── */
function GraphViewport({ data, selected, onSelect }: {
  data: GraphData; selected: string | null; onSelect: (key: string | null) => void
}) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [size, setSize] = useState({ width: 900, height: 620 })
  const [layout, setLayout] = useState<{ nodes: SimNode[]; links: SimLink[] }>({ nodes: [], links: [] })
  const [transform, setTransform] = useState<TransformState>({ x: 0, y: 0, scale: 1 })
  const dragState = useRef<{ x: number; y: number; tx: number; ty: number; moved: boolean } | null>(null)
  const simRef = useRef<ReturnType<typeof forceSimulation> | null>(null)
  const positionsRef = useRef<Map<string, { x: number; y: number }>>(new Map())
  const isFirstLoad = useRef(true)

  // Memoized degree map — declared before useEffects that use it
  const degree = useMemo<Record<string, number>>(() => {
    const d: Record<string, number> = {}
    data.links.forEach(l => {
      const s = String(l.source), t = String(l.target)
      d[s] = (d[s] || 0) + 1
      d[t] = (d[t] || 0) + 1
    })
    return d
  }, [data.links])

  useEffect(() => {
    const container = containerRef.current
    if (!container) return
    const updateSize = () => {
      const rect = container.getBoundingClientRect()
      setSize({ width: Math.max(rect.width, 320), height: Math.max(rect.height, 420) })
    }
    updateSize()
    const observer = new ResizeObserver(updateSize)
    observer.observe(container)
    return () => observer.disconnect()
  }, [])

  // Refs for live nodes/links — tick callback reads from these so warm updates work
  const nodesRef = useRef<SimNode[]>([])
  const linksRef = useRef<SimLink[]>([])

  /** Build nodes array, preserving positions for known nodes */
  const buildNodes = (incoming: GraphData['nodes']): SimNode[] => {
    const pos = positionsRef.current
    return incoming.map(node => {
      const saved = pos.get(node.key)
      if (saved) return { ...node, x: saved.x, y: saved.y, vx: 0, vy: 0 }
      // New node — spawn near connected neighbour if possible
      const nbLink = data.links.find(
        l => (String(l.source) === node.key && pos.has(String(l.target)))
          || (String(l.target) === node.key && pos.has(String(l.source)))
      )
      if (nbLink) {
        const nKey = String(nbLink.source) === node.key ? String(nbLink.target) : String(nbLink.source)
        const nPos = pos.get(nKey)!
        return { ...node, x: nPos.x + (Math.random() - 0.5) * 80, y: nPos.y + (Math.random() - 0.5) * 80 }
      }
      return { ...node, x: size.width / 2 + (Math.random() - 0.5) * 100, y: size.height / 2 + (Math.random() - 0.5) * 100 }
    })
  }

  /** Cold start: create simulation from scratch (first load / resize) */
  useEffect(() => {
    if (!size.width || !size.height) return

    const nodes = buildNodes(data.nodes)
    const keySet = new Set(nodes.map(n => n.key))
    const links: SimLink[] = data.links
      .filter(l => keySet.has(String(l.source)) && keySet.has(String(l.target)))
      .map(l => ({ ...l }))

    nodesRef.current = nodes
    linksRef.current = links

    if (simRef.current) simRef.current.stop()

    const sim = forceSimulation<SimNode>(nodes)
      .force('charge', forceManyBody<SimNode>().strength(n => -(nodeRadius(degree[n.key] || 0) ** 2 * 18)))
      .force('link', forceLink<SimNode, SimLink>(links)
        .id(n => n.key)
        .distance(link => {
          const rs = nodeRadius(degree[(link.source as SimNode).key] || 0)
          const rt = nodeRadius(degree[(link.target as SimNode).key] || 0)
          return rs + rt + 60
        })
        .strength(0.4)
      )
      .force('center', forceCenter(size.width / 2, size.height / 2).strength(0.04))
      .force('collide', forceCollide<SimNode>(n => {
        const r = nodeRadius(degree[n.key] || 0)
        return r + Math.min(n.name.length, 20) * 3.5 + 8
      }).strength(0.85).iterations(4))
      .force('x', forceX<SimNode>(size.width / 2).strength(0.02))
      .force('y', forceY<SimNode>(size.height / 2).strength(0.02))
      .alpha(1).alphaDecay(0.022).velocityDecay(0.42)

    sim.on('tick', () => {
      const ns = nodesRef.current
      const pos = positionsRef.current
      ns.forEach(n => { if (n.x != null && n.y != null) pos.set(n.key, { x: n.x, y: n.y }) })
      setLayout({ nodes: [...ns], links: [...linksRef.current] })
    })

    simRef.current = sim
    setTransform({ x: 0, y: 0, scale: 1 })
    isFirstLoad.current = false

    return () => sim.stop()
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [size.width, size.height])

  /** Warm update: when data changes, reheat existing sim without recreating */
  useEffect(() => {
    if (!size.width || !size.height || isFirstLoad.current) return
    const sim = simRef.current
    if (!sim) return

    sim.stop()

    const nodes = buildNodes(data.nodes)
    const keySet = new Set(nodes.map(n => n.key))
    const links: SimLink[] = data.links
      .filter(l => keySet.has(String(l.source)) && keySet.has(String(l.target)))
      .map(l => ({ ...l }))

    nodesRef.current = nodes
    linksRef.current = links

    // Update forces with new data
    ;(sim as any).nodes(nodes)
    const linkForce = (sim as any).force('link')
    if (linkForce) linkForce.links(links)
    sim.force('charge', forceManyBody<SimNode>().strength(n => -(nodeRadius(degree[n.key] || 0) ** 2 * 18)))
    sim.force('collide', forceCollide<SimNode>(n => {
      const r = nodeRadius(degree[n.key] || 0)
      return r + Math.min(n.name.length, 20) * 3.5 + 8
    }).strength(0.85).iterations(4))

    // Gentle reheat — existing nodes barely move, new ones settle in
    const newCount = nodes.filter(n => !positionsRef.current.has(n.key) || n.vx !== 0).length
    const warmAlpha = newCount > 0 ? 0.3 : 0.1
    ;(sim as any).alpha(warmAlpha).restart()
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data, degree])

  function resetView() { setTransform({ x: 0, y: 0, scale: 1 }) }
  function zoom(delta: number) {
    setTransform(prev => ({ ...prev, scale: clamp(prev.scale + delta, MIN_SCALE, MAX_SCALE) }))
  }

  function handleWheel(e: React.WheelEvent<SVGSVGElement>) {
    e.preventDefault()
    const factor = e.deltaY > 0 ? -0.1 : 0.1
    setTransform(prev => {
      const newScale = clamp(prev.scale + factor, MIN_SCALE, MAX_SCALE)
      return { ...prev, scale: newScale }
    })
  }

  function handlePointerDown(e: React.PointerEvent<SVGSVGElement>) {
    dragState.current = { x: e.clientX, y: e.clientY, tx: transform.x, ty: transform.y, moved: false }
  }
  function handlePointerMove(e: React.PointerEvent<SVGSVGElement>) {
    const d = dragState.current
    if (!d) return
    const dx = e.clientX - d.x, dy = e.clientY - d.y
    if (Math.abs(dx) > 3 || Math.abs(dy) > 3) d.moved = true
    if (d.moved) setTransform(prev => ({ ...prev, x: d.tx + dx, y: d.ty + dy }))
  }
  function handlePointerUp() { dragState.current = null }

  return (
    <div ref={containerRef} style={{ position: 'relative', height: '100%', width: '100%' }}>

      {/* Zoom controls */}
      <div style={{ position: 'absolute', left: '14px', top: '14px', zIndex: 10, display: 'flex', flexDirection: 'column', gap: '4px' }}>
        {[{ label: '+', fn: () => zoom(0.15) }, { label: '−', fn: () => zoom(-0.15) }, { label: '⊙', fn: resetView }].map(btn => (
          <button key={btn.label} type="button" onClick={btn.fn} style={{
            width: '28px', height: '28px',
            background: 'var(--color-obsidian)', border: '1px solid var(--color-graphite)', borderRadius: 0,
            color: 'var(--color-chalk)', fontFamily: "'Red Hat Mono', monospace",
            fontSize: btn.label === '⊙' ? '13px' : '16px',
            cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center',
            transition: 'border-color 0.15s, color 0.15s',
          }}
            onMouseEnter={e => { (e.currentTarget as HTMLButtonElement).style.borderColor = 'var(--color-chalk)'; (e.currentTarget as HTMLButtonElement).style.color = '#ffffff' }}
            onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.borderColor = 'var(--color-graphite)'; (e.currentTarget as HTMLButtonElement).style.color = 'var(--color-chalk)' }}
          >{btn.label}</button>
        ))}
      </div>

      {/* Hint */}
      <div style={{
        position: 'absolute', bottom: '12px', left: '14px', zIndex: 10,
        background: 'var(--color-obsidian)', border: '1px solid var(--color-graphite)',
        borderRadius: 0, padding: '4px 10px',
        fontFamily: "var(--font-aeonik)", fontSize: '11px', color: 'var(--color-smoke)',
      }}>
        колесо: зум · перетаскивание: панорама · клик: детали
      </div>

      {/* Scale indicator */}
      <div style={{
        position: 'absolute', bottom: '12px', right: '14px', zIndex: 10,
        background: 'var(--color-obsidian)', border: '1px solid var(--color-graphite)',
        borderRadius: 0, padding: '4px 10px',
        fontFamily: "var(--font-aeonik)", fontSize: '11px', color: 'var(--color-smoke)',
      }}>
        {Math.round(transform.scale * 100)}%
      </div>

      <svg
        className="graph-canvas"
        viewBox={`0 0 ${size.width} ${size.height}`}
        style={{ height: '100%', width: '100%', userSelect: 'none' }}
        aria-label="Граф знаний"
        onClick={() => onSelect(null)}
        onWheel={handleWheel}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onPointerCancel={() => { dragState.current = null }}
      >
        <defs>
          {/* Arrow marker */}
          <marker id="arrow" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto">
            <path d="M0,0 L0,6 L6,3 z" fill="var(--color-chalk)" />
          </marker>
        </defs>

        {/* Space Background */}
        <rect width="100%" height="100%" fill="var(--graph-background)" pointerEvents="none" />

        <g transform={`translate(${transform.x} ${transform.y}) scale(${transform.scale})`}>


          {/* Constellation Starfield */}
          <g opacity={0.95} pointerEvents="none">
            {STARS.map(star => (
              <circle
                key={`star-${star.id}`}
                cx={star.x}
                cy={star.y}
                r={star.r}
                fill={star.color}
                opacity={star.opacity}
                className={star.twinkleClass}
              />
            ))}
          </g>

          {/* Links */}
          {layout.links.map((link, idx) => {
            const source = link.source as SimNode
            const target = link.target as SimNode
            if (source.x == null || source.y == null || target.x == null || target.y == null) return null
            const isRelatedToSelected = selected && (source.key === selected || target.key === selected)
            const isDimmed = selected && !isRelatedToSelected
            
            return (
              <path
                id={`edge-${source.key}-${target.key}-${idx}`}
                key={`path-${source.key}-${target.key}-${link.type}-${idx}`}
                d={`M ${source.x} ${source.y} L ${target.x} ${target.y}`}
                stroke={isRelatedToSelected ? 'var(--color-chalk)' : isDimmed ? 'var(--color-carbon)' : 'var(--color-graphite)'}
                strokeWidth={isRelatedToSelected ? 2 : 1}
                fill="none"
                markerEnd={isRelatedToSelected ? 'url(#arrow)' : undefined}
                style={{ transition: 'stroke 0.3s, stroke-width 0.3s' }}
              />
            )
          })}

          {/* Animated Edge Particles */}
          {selected && layout.links.map((link, idx) => {
            const source = link.source as SimNode
            const target = link.target as SimNode
            const isRelated = source.key === selected || target.key === selected
            if (!isRelated || source.x == null || source.y == null || target.x == null || target.y == null) return null
            return (
              <circle key={`particle-${idx}`} r="2.5" fill="var(--color-chalk)">
                <animateMotion dur="1.2s" repeatCount="indefinite">
                  <mpath href={`#edge-${source.key}-${target.key}-${idx}`} />
                </animateMotion>
              </circle>
            )
          })}

          {/* Nodes */}
          {layout.nodes.map(node => {
            if (node.x == null || node.y == null) return null
            const isSelected = node.key === selected
            const isRelated = selected && !isSelected && layout.links.some(l => {
              const s = l.source as SimNode, t = l.target as SimNode
              return (s.key === selected && t.key === node.key) || (t.key === selected && s.key === node.key)
            })
            const color = ENTITY_TYPE_COLORS[node.type] || 'var(--color-smoke)'
            const r = nodeRadius(degree[node.key] || 0)
            const labelLines = wrapNodeLabel(node.name)
            const labelWidth = Math.max(...labelLines.map(line => line.length)) * 7.5 + 20
            const labelHeight = labelLines.length === 1 ? 26 : 40
            const dimmed = selected && !isSelected && !isRelated
            const showDetails = transform.scale >= 0.4 || isSelected || isRelated

            return (
              <g
                key={node.key}
                transform={`translate(${node.x} ${node.y})`}
                onClick={e => { e.stopPropagation(); onSelect(node.key) }}
                style={{ cursor: 'pointer', opacity: dimmed ? 0.22 : 1, transition: 'opacity 0.2s' }}
              >
                {/* Fake glow layers instead of expensive SVG filters */}
                {(isSelected || isRelated) && (
                  <>
                    <circle r={r + (isSelected ? 10 : 5)} fill={color} opacity={isSelected ? 0.15 : 0.1} />
                    <circle r={r + (isSelected ? 5 : 2.5)} fill={color} opacity={isSelected ? 0.3 : 0.2} />
                  </>
                )}

                {/* Outer orbital ring (animated) - LOD applied */}
                {isSelected && showDetails && (
                  <circle r={r + 12} fill="none" stroke={color} strokeWidth={1} strokeDasharray="4 6" opacity={0.8}>
                    <animateTransform attributeName="transform" type="rotate" from="0" to="360" dur="8s" repeatCount="indefinite" />
                  </circle>
                )}
                {isSelected && showDetails && (
                  <circle r={r + 20} fill="none" stroke={color} strokeWidth={0.5} strokeDasharray="1 8" opacity={0.5}>
                    <animateTransform attributeName="transform" type="rotate" from="360" to="0" dur="12s" repeatCount="indefinite" />
                  </circle>
                )}

                {/* Node body (core) */}
                <circle
                  r={r}
                  fill={color}
                  stroke={isSelected ? '#ffffff' : isRelated ? color : 'rgba(255,255,255,0.2)'}
                  strokeWidth={isSelected ? 2.5 : isRelated ? 1.5 : 1}
                />

                {/* Inner highlight core */}
                <circle r={r * 0.4} fill="#ffffff" opacity={isSelected ? 0.9 : 0.4} />

                {/* Fast Label pill (No backdrop-filter blur for perf) - LOD applied */}
                {showDetails && (
                  <g transform={`translate(${r + 8} ${-labelHeight / 2})`}>
                    <rect
                      width={labelWidth}
                      height={labelHeight}
                      rx={labelHeight / 2}
                      fill={isSelected ? 'var(--graph-node-label-selected)' : 'var(--graph-node-label-bg)'}
                      stroke={isSelected ? color : 'var(--graph-node-label-border)'}
                      strokeWidth={isSelected ? 1.5 : 1}
                      style={{ transition: 'fill 0.2s, stroke 0.2s' }}
                    />
                    <text
                      x={10} y={labelLines.length === 1 ? 17 : 15}
                      fill={isSelected ? 'var(--graph-node-label-selected-text)' : isRelated ? 'var(--graph-node-label-related-text)' : 'var(--graph-node-label-text)'}
                      fontSize="12"
                      fontFamily="var(--font-aeonik)"
                      fontWeight={isSelected ? '600' : '500'}
                      letterSpacing="0.02em"
                    >
                      {labelLines.map((line, index) => (
                        <tspan key={index} x={10} dy={index === 0 ? 0 : 14}>{line}</tspan>
                      ))}
                    </text>
                  </g>
                )}

                {/* Type dot in corner - LOD applied */}
                {showDetails && (
                  <circle r={2.5} cx={r * 0.6} cy={-r * 0.6} fill="rgba(0,0,0,0.5)" stroke={color} strokeWidth={1} />
                )}
              </g>
            )
          })}
        </g>
      </svg>
    </div>
  )
}

/* ── Entity Panel ── */
function EntityPanel({ entityKey, details, onDocSelect }: { entityKey: string; details: EntityDetails; onDocSelect?: (docName: string) => void }) {
  const [exporting, setExporting] = useState(false)

  async function handleExportJsonLd() {
    setExporting(true)
    try {
      await exportJsonLdEntity(entityKey)
    } catch (e) {
      console.error('JSON-LD export failed:', e)
    } finally {
      setExporting(false)
    }
  }
  const factItems = details.facts.filter(f => f && f.predicate && f.object && !f.object.toLowerCase().includes('не указан'))
  const relationItems = (details.relations || []).filter(r => r.key && r.name)
  const color = ENTITY_TYPE_COLORS[details.type] || 'var(--color-smoke)'

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>

      {/* Header card */}
      <div style={{
        background: 'var(--color-obsidian)',
        border: '1px solid var(--color-graphite)',
        borderTop: `2px solid ${color}`,
        borderRadius: 0, padding: '24px',
        display: 'flex', flexDirection: 'column', gap: '0',
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <span style={{
          display: 'inline-flex', alignItems: 'center', gap: '6px',
          background: 'var(--color-obsidian)', border: '1px solid var(--color-graphite)',
          borderRadius: 0, padding: '4px 8px',
          fontFamily: "var(--font-aeonik)", fontSize: '11px',
          textTransform: 'uppercase', color: 'var(--color-smoke)',
        }}>
          <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: color, display: 'inline-block' }} />
          {ENTITY_TYPE_LABELS[details.type] || details.type}
        </span>
          <button
            type="button"
            onClick={handleExportJsonLd}
            disabled={exporting}
            style={{
              fontFamily: "var(--font-helvetica-now-text)", fontSize: '11px',
              color: exporting ? 'var(--color-graphite)' : 'var(--color-smoke)',
              background: 'transparent', border: '1px solid var(--color-graphite)',
              padding: '4px 8px', cursor: exporting ? 'default' : 'pointer',
              display: 'flex', alignItems: 'center', gap: '4px',
              transition: 'all 0.2s', borderRadius: 0,
            }}
            onMouseEnter={e => { if (!exporting) { e.currentTarget.style.borderColor = 'var(--color-chalk)'; e.currentTarget.style.color = '#ffffff' } }}
            onMouseLeave={e => { if (!exporting) { e.currentTarget.style.borderColor = 'var(--color-graphite)'; e.currentTarget.style.color = 'var(--color-smoke)' } }}
            title="Экспорт сущности в JSON-LD"
          >
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/>
              <polyline points="7 10 12 15 17 10"/>
              <line x1="12" y1="15" x2="12" y2="3"/>
            </svg>
            {exporting ? '...' : 'JSON-LD'}
          </button>
        </div>
        <h3 style={{
          marginTop: '16px', fontFamily: "var(--font-aeonik)",
          fontSize: '18px', fontWeight: 400, color: '#ffffff',
          lineHeight: 1.3, margin: '16px 0 0 0'
        }}>{details.name}</h3>
        {details.description && (
          <p style={{
            marginTop: '12px', fontFamily: "var(--font-aeonik)",
            fontSize: '14px', lineHeight: 1.6, color: 'var(--color-chalk)',
            margin: '12px 0 0 0'
          }}>{details.description}</p>
        )}
      </div>

      {/* Facts */}
      {factItems.length > 0 && (
        <div>
          <SectionLabel>Факты · {factItems.length}</SectionLabel>
          <ul style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginTop: '12px', listStyle: 'none', padding: 0 }}>
            {factItems.map((fact, i) => (
              <li key={i} style={{
                background: 'var(--color-obsidian)', border: '1px solid var(--color-graphite)',
                borderRadius: 0, padding: '14px', transition: 'background 0.2s',
              }}
              onMouseEnter={e => { (e.currentTarget as HTMLLIElement).style.background = 'transparent' }}
              onMouseLeave={e => { (e.currentTarget as HTMLLIElement).style.background = 'var(--color-obsidian)' }}
              >
                <p style={{ fontFamily: "var(--font-aeonik)", fontSize: '13px', color: 'var(--color-smoke)', marginBottom: '4px', margin: 0 }}>
                  {fact.predicate}
                </p>
                <p style={{ fontFamily: "var(--font-aeonik)", fontSize: '14px', color: '#ffffff', fontWeight: 400, margin: 0 }}>
                  {fact.value_min != null
                    ? fact.value_min === fact.value_max
                      ? `${fact.value_min} ${fact.unit || ''}`
                      : `${fact.value_min}–${fact.value_max} ${fact.unit || ''}`
                    : fact.object}
                </p>
                <div style={{ display: 'flex', gap: '12px', marginTop: '8px', alignItems: 'center' }}>
                  <span style={{ fontFamily: "var(--font-aeonik)", fontSize: '11px', color: 'var(--color-smoke)' }}>
                    {Math.round((fact.confidence ?? 0.5) * 100)}%
                    {fact.geography && fact.geography !== 'unknown' ? ` · ${fact.geography}` : ''}
                  </span>
                </div>
                {fact.quote && (
                  <p style={{ marginTop: '8px', fontFamily: "var(--font-aeonik)", fontSize: '13px', fontStyle: 'italic', color: 'var(--color-chalk)', lineHeight: 1.5, borderLeft: '2px solid var(--color-graphite)', paddingLeft: '12px', margin: '8px 0 0 0' }}>"{fact.quote}"</p>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Documents */}
      {details.documents.filter(Boolean).length > 0 && (
        <div>
          <SectionLabel>Источники</SectionLabel>
          <ul style={{ display: 'flex', flexDirection: 'column', gap: '6px', marginTop: '12px', listStyle: 'none', padding: 0 }}>
            {details.documents.filter(Boolean).map(doc => (
              <li key={doc} onClick={() => onDocSelect?.(doc)} style={{
                background: 'var(--color-obsidian)', border: '1px solid var(--color-graphite)',
                borderRadius: 0, padding: '10px 14px', fontFamily: "var(--font-aeonik)",
                fontSize: '13px', color: 'var(--color-chalk)', cursor: 'pointer',
                display: 'flex', alignItems: 'center', gap: '10px', transition: 'all 0.2s'
              }}
              onMouseEnter={e => { (e.currentTarget as HTMLLIElement).style.background = 'transparent'; (e.currentTarget as HTMLLIElement).style.borderColor = 'var(--color-graphite)' }}
              onMouseLeave={e => { (e.currentTarget as HTMLLIElement).style.background = 'var(--color-obsidian)'; (e.currentTarget as HTMLLIElement).style.borderColor = 'var(--color-graphite)' }}
              >
                <span style={{ color: 'var(--color-chalk)', fontSize: '14px', opacity: 0.8 }}>📄</span>
                {doc}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Relations */}
      {relationItems.length > 0 && (
        <div style={{ paddingBottom: '20px' }}>
          <SectionLabel>Связи · {Math.min(relationItems.length, 12)}</SectionLabel>
          <ul style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginTop: '12px', listStyle: 'none', padding: 0 }}>
            {relationItems.slice(0, 12).map((rel, i) => {
              const rc = ENTITY_TYPE_COLORS[rel.entity_type || ''] || 'var(--color-smoke)'
              return (
                <li key={i} style={{
                  background: 'var(--color-obsidian)', border: '1px solid var(--color-graphite)',
                  borderRadius: 0, padding: '12px 14px', display: 'flex', alignItems: 'center', gap: '12px',
                  transition: 'background 0.2s', cursor: 'default'
                }}
                onMouseEnter={e => { (e.currentTarget as HTMLLIElement).style.background = 'transparent' }}
                onMouseLeave={e => { (e.currentTarget as HTMLLIElement).style.background = 'var(--color-obsidian)' }}
                >
                  <span style={{
                    fontFamily: "var(--font-aeonik)", fontSize: '14px',
                    color: 'var(--color-smoke)',
                  }}>
                    {rel.direction === 'in' ? '←' : '→'}
                  </span>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <p style={{ fontFamily: "var(--font-aeonik)", fontSize: '11px', color: 'var(--color-smoke)', textTransform: 'uppercase', margin: 0, marginBottom: '2px' }}>
                      {rel.type}
                    </p>
                    <p style={{ fontFamily: "var(--font-aeonik)", fontSize: '13px', color: '#ffffff', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', margin: 0 }}>
                      {rel.name}
                    </p>
                  </div>
                  <span style={{
                    width: '8px', height: '8px', borderRadius: '50%',
                    background: rc, flexShrink: 0
                  }} />
                </li>
              )
            })}
          </ul>
        </div>
      )}
    </div>
  )
}

/* ── FilterChip ── */
function FilterChip({ active, color, children, onClick }: {
  active: boolean; color: string; children: ReactNode; onClick: () => void
}) {
  return (
    <button
      type="button"
      className={`graph-filter${active ? ' active' : ''}`}
      onClick={onClick}
      style={{
        display: 'inline-flex', alignItems: 'center', gap: '8px',
        padding: '7px 11px', borderRadius: 0,
        background: active ? '#252624' : 'var(--control-bg)',
        border: `1px solid ${active ? '#252624' : 'var(--control-border)'}`,
        color: active ? '#ffffff' : 'var(--control-text)',
        fontFamily: "var(--font-helvetica-now-text)",
        fontSize: '12px', fontWeight: 400,
        cursor: 'pointer', transition: 'all 0.15s',
      }}
    >
      <span style={{ 
        width: '6px', height: '6px', borderRadius: '50%', 
        background: active ? color : 'var(--color-smoke)', flexShrink: 0,
      }} />
      {children}
    </button>
  )
}

/* ── StateMessage ── */
function StateMessage({ children, icon = '◎' }: { children: ReactNode; icon?: string }) {
  return (
    <div style={{ position: 'relative', zIndex: 10, display: 'flex', height: '100%', alignItems: 'center', justifyContent: 'center', padding: '24px' }}>
      <div className="frosted-panel" style={{
        maxWidth: '400px', textAlign: 'center',
        border: '1px solid rgba(37, 48, 68, 0.92)',
        borderRadius: 0, padding: '32px 40px',
      }}>
        <div style={{ fontFamily: "var(--font-aeonik)", fontSize: '24px', color: '#ffffff', marginBottom: '16px' }}>{icon}</div>
        <p style={{ fontFamily: "var(--font-aeonik)", fontSize: '14px', color: 'var(--color-chalk)', lineHeight: 1.6, margin: 0 }}>{children}</p>
      </div>
    </div>
  )
}

/* ── EmptyPane ── */
function EmptyPane({ children, icon = '◈', color = 'var(--color-smoke)', pulse = false }: {
  children: ReactNode; icon?: string; color?: string; pulse?: boolean
}) {
  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', textAlign: 'center', padding: '32px', gap: '16px' }}>
      <span style={{ fontFamily: "var(--font-aeonik)", fontSize: '24px', color: color }}>{icon}</span>
      <p style={{ fontFamily: "var(--font-aeonik)", fontSize: '14px', color: 'var(--color-smoke)', lineHeight: 1.6, margin: 0 }}>{children}</p>
    </div>
  )
}

/* ── SectionLabel ── */
function SectionLabel({ children }: { children: ReactNode }) {
  return (
    <div style={{
      fontFamily: "var(--font-aeonik)",
      fontSize: '12px', fontWeight: 400, textTransform: 'uppercase',
      color: 'var(--color-smoke)', margin: 0
    }}>{children}</div>
  )
}

function clamp(v: number, min: number, max: number) { return Math.min(max, Math.max(min, v)) }

/* ── DocumentReaderModal ── */
function DocumentReaderModal({ docName, onClose }: { docName: string; onClose: () => void }) {
  const { data, error, isLoading } = useSWR<{ content: string }>(
    `/api/documents/${encodeURIComponent(docName)}/content`,
    fetcher
  )
  const [mounted, setMounted] = useState(false)

  // Prevent scroll on body and handle Escape key
  useEffect(() => {
    setMounted(true)
    const originalStyle = window.getComputedStyle(document.body).overflow
    document.body.style.overflow = 'hidden'

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handleKeyDown)

    return () => {
      document.body.style.overflow = originalStyle
      window.removeEventListener('keydown', handleKeyDown)
    }
  }, [onClose])

  if (!mounted) return null

  const modalContent = (
    <div 
      className="animate-fade-in"
      onClick={onClose}
      style={{
        position: 'fixed', inset: 0, zIndex: 2147483647,
        background: 'rgba(15, 16, 26, 0.85)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        padding: '16px', backdropFilter: 'blur(4px)',
      }}
    >
      <div 
        className="animate-fade-in-scale"
        onClick={e => e.stopPropagation()}
        style={{
          background: 'var(--color-obsidian)', border: '1px solid var(--color-graphite)',
          borderRadius: 0, width: '100%', maxWidth: '1000px',
          height: '90vh', display: 'flex', flexDirection: 'column',
          boxShadow: '0 24px 48px rgba(0,0,0,0.5)',
          position: 'relative',
        }}
      >
        {/* Header */}
        <div style={{
          padding: '20px 24px', borderBottom: '1px solid var(--color-graphite)',
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          flexShrink: 0,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', minWidth: 0 }}>
            <span style={{ color: 'var(--color-chalk)', fontSize: '20px', flexShrink: 0 }}>📄</span>
            <h2 style={{
              fontFamily: "var(--font-aeonik)", fontSize: '18px',
              fontWeight: 400, color: '#ffffff', margin: 0,
              whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis'
            }}>{docName}</h2>
          </div>
          <button onClick={onClose} style={{
            background: 'transparent', border: 'none', color: 'var(--color-smoke)',
            cursor: 'pointer', fontSize: '28px', lineHeight: 1, padding: '4px 12px',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            transition: 'color 0.2s', flexShrink: 0, marginLeft: '12px'
          }} onMouseEnter={e => (e.currentTarget.style.color = '#ffffff')}
             onMouseLeave={e => (e.currentTarget.style.color = 'var(--color-smoke)')}
          >×</button>
        </div>

        {/* Content */}
        <div style={{
          padding: '24px 32px', overflowY: 'auto', flex: 1,
          fontFamily: "var(--font-aeonik)",
          fontSize: '15px', lineHeight: 1.7, color: 'var(--color-chalk)',
        }}>
          {isLoading ? (
            <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%', color: 'var(--color-smoke)' }}>
              <span style={{ animation: 'pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite' }}>Loading document...</span>
            </div>
          ) : error ? (
            <div style={{ color: '#ef4444', textAlign: 'center', padding: '40px' }}>
              Failed to load document content.
            </div>
          ) : !data?.content ? (
            <div style={{ color: 'var(--color-smoke)', textAlign: 'center', padding: '40px' }}>
              No text content extracted for this document.
            </div>
          ) : (
            <div style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
              {data.content}
            </div>
          )}
        </div>
      </div>
    </div>
  )

  return createPortal(modalContent, document.body)
}
