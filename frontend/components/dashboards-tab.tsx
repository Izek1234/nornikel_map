'use client'

import { useState } from 'react'
import useSWR from 'swr'
import { fetcher, exportJsonLdFull } from '@/lib/api'
import { Activity, BarChart2, Users, FileText, BrainCircuit, Network, Database, Layers } from 'lucide-react'

const DEFAULT_STATS = {
  documents: 0,
  entities: 0,
  facts: 0,
  chunks: 0,
  relations: 0,
  experiments: 0,
  materials: 0,
  publications: 0,
  experts: 0,
  facilities: 0,
}

const DEFAULT_GAPS = {
  gaps: [],
  total_gaps: 0,
  coverage: 0.85,
}

export function DashboardsTab() {
  const [exporting, setExporting] = useState(false)
  const { data: statsData, isLoading: isStatsLoading } = useSWR<any>('/api/stats', fetcher, { refreshInterval: 15000 })
  const { data: gapsData, isLoading: isGapsLoading } = useSWR<any>('/api/gaps', fetcher, { refreshInterval: 15000 })

  async function handleExportFull() {
    setExporting(true)
    try {
      await exportJsonLdFull(500)
    } catch (e) {
      console.error('JSON-LD export failed:', e)
    } finally {
      setExporting(false)
    }
  }

  const stats = statsData || DEFAULT_STATS
  const gapsInfo = gapsData || DEFAULT_GAPS

  const realMetrics = [
    { label: 'Обработано документов', value: stats.documents.toString(), change: 'Всего в системе', icon: FileText, color: 'var(--color-chalk)' },
    { label: 'Узлов сущностей в графе', value: stats.entities.toLocaleString('ru-RU'), change: `Фактов: ${stats.facts}`, icon: Network, color: 'var(--color-compass-gold)' },
    { label: 'Связей в нейро-графе', value: stats.relations.toLocaleString('ru-RU'), change: 'Всего ребер', icon: Layers, color: 'var(--color-chalk)' },
    { label: 'Полнота базы знаний', value: `${Math.round(gapsInfo.coverage * 100)}%`, change: `Разрывов: ${gapsInfo.total_gaps}`, icon: BrainCircuit, color: 'var(--color-compass-gold)' },
  ]

  return (
    <div style={{ padding: '20px 0', fontFamily: 'var(--font-aeonik)' }}>
      {/* Export bar */}
      <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: '16px' }}>
        <button
          type="button"
          onClick={handleExportFull}
          disabled={exporting}
          style={{
            fontFamily: "var(--font-helvetica-now-text)", fontSize: '12px',
            color: exporting ? 'var(--color-graphite)' : 'var(--color-smoke)',
            background: 'transparent', border: '1px solid var(--color-graphite)',
            padding: '6px 12px', cursor: exporting ? 'default' : 'pointer',
            display: 'flex', alignItems: 'center', gap: '6px',
            transition: 'all 0.2s', borderRadius: 0,
          }}
          onMouseEnter={e => { if (!exporting) { e.currentTarget.style.borderColor = 'var(--color-chalk)'; e.currentTarget.style.color = '#ffffff' } }}
          onMouseLeave={e => { if (!exporting) { e.currentTarget.style.borderColor = 'var(--color-graphite)'; e.currentTarget.style.color = 'var(--color-smoke)' } }}
          title="Экспорт полного графа знаний в JSON-LD"
        >
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/>
            <polyline points="7 10 12 15 17 10"/>
            <line x1="12" y1="15" x2="12" y2="3"/>
          </svg>
          {exporting ? 'Экспорт...' : 'Экспорт полного графа (JSON-LD)'}
        </button>
      </div>

      <div style={{ 
        display: 'grid', 
        gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', 
        gap: '20px',
        marginBottom: '32px'
      }}>
        {realMetrics.map((m, i) => (
          <div key={i} style={{
            background: 'transparent',
            border: '1px solid var(--color-graphite)',
            borderRadius: 0,
            padding: '20px',
            display: 'flex',
            flexDirection: 'column',
            position: 'relative',
            overflow: 'hidden'
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '16px' }}>
              <div style={{ 
                width: '40px', 
                height: '40px', 
                borderRadius: 0, 
                border: '1px solid var(--color-graphite)',
                background: 'transparent', 
                display: 'flex', 
                alignItems: 'center', 
                justifyContent: 'center',
                color: m.color
              }}>
                <m.icon size={20} />
              </div>
              <span style={{ 
                fontFamily: 'var(--font-mono)',
                fontSize: '12px', 
                fontWeight: 400, 
                color: 'var(--color-smoke)',
                border: '1px solid var(--color-graphite)',
                background: 'transparent',
                padding: '4px 8px',
                borderRadius: 0
              }}>
                {m.change}
              </span>
            </div>
            
            <h3 style={{ fontSize: '28px', fontWeight: 400, color: 'var(--color-chalk)', margin: '0 0 4px 0', fontFamily: 'var(--font-mono)' }}>
              {isStatsLoading && !statsData ? 'Загрузка...' : m.value}
            </h3>
            <p style={{ color: 'var(--color-smoke)', margin: 0, fontSize: '13px', fontWeight: 400 }}>{m.label}</p>
          </div>
        ))}
      </div>

      <div style={{ 
        display: 'grid', 
        gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))', 
        gap: '20px'
      }}>
        {/* Coverage Chart */}
        <div style={{
          background: 'transparent',
          border: '1px solid var(--color-graphite)',
          borderRadius: 0,
          padding: '24px',
          display: 'flex',
          flexDirection: 'column'
        }}>
          <h3 style={{ fontSize: '16px', fontWeight: 400, color: 'var(--color-chalk)', margin: '0 0 24px 0', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <BarChart2 size={18} color="var(--color-compass-gold)" />
            Распределение сущностей в графе знаний
          </h3>
          
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            {[
              { name: 'Эксперименты (Experiment)', val: stats.experiments, maxVal: Math.max(stats.entities, 1), color: 'var(--color-chalk)' },
              { name: 'Материалы (Material)', val: stats.materials, maxVal: Math.max(stats.entities, 1), color: 'var(--color-smoke)' },
              { name: 'Публикации (Publication)', val: stats.publications, maxVal: Math.max(stats.entities, 1), color: 'var(--color-compass-gold)' },
              { name: 'Эксперты (Expert)', val: stats.experts, maxVal: Math.max(stats.entities, 1), color: 'var(--color-iron)' },
              { name: 'Установки (Facility)', val: stats.facilities, maxVal: Math.max(stats.entities, 1), color: '#8B5CF6' },
            ].map(item => {
              const percentage = Math.round((item.val / item.maxVal) * 100)
              return (
                <div key={item.name} style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '13px', color: 'var(--color-chalk)' }}>
                    <span>{item.name}</span>
                    <span style={{ fontWeight: 400, fontFamily: 'var(--font-mono)' }}>{item.val} ед. ({percentage}%)</span>
                  </div>
                  <div style={{ width: '100%', height: '8px', border: '1px solid var(--color-graphite)', borderRadius: 0, overflow: 'hidden' }}>
                    <div style={{ width: `${percentage}%`, height: '100%', background: item.color, borderRadius: 0 }} />
                  </div>
                </div>
              )
            })}
          </div>
        </div>

        {/* Risk Zones */}
        <div style={{
          background: 'transparent',
          border: '1px solid var(--color-graphite)',
          borderRadius: 0,
          padding: '24px',
          display: 'flex',
          flexDirection: 'column'
        }}>
          <h3 style={{ fontSize: '16px', fontWeight: 400, color: 'var(--color-chalk)', margin: '0 0 24px 0', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Activity size={18} color="var(--color-compass-gold)" />
            Зоны риска (мало источников / низкая достоверность)
          </h3>
          
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', overflowY: 'auto', maxHeight: '320px' }}>
            {isGapsLoading && !gapsData ? (
              <p style={{ color: 'var(--color-smoke)', fontSize: '13px' }}>Загрузка зон риска...</p>
            ) : gapsInfo.gaps.length === 0 ? (
              <p style={{ color: 'var(--color-smoke)', fontSize: '13px' }}>Зоны риска не обнаружены. Покрытие знаний 100%!</p>
            ) : (
              gapsInfo.gaps.slice(0, 6).map((r: any, i: number) => (
                <div key={i} style={{ padding: '12px', background: 'transparent', border: `1px solid var(--color-graphite)`, borderRadius: 0 }}>
                  <div style={{ color: 'var(--color-chalk)', fontSize: '13px', fontWeight: 400, marginBottom: '4px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ fontWeight: 500 }}>{r.topic}</span>
                    <span style={{
                      fontSize: '10px',
                      padding: '1px 5px',
                      background: r.severity === 'high' ? 'rgba(239, 68, 68, 0.15)' : 'rgba(245, 158, 11, 0.15)',
                      color: r.severity === 'high' ? '#ef4444' : '#f59e0b',
                      border: `1px solid ${r.severity === 'high' ? '#ef4444' : '#f59e0b'}`,
                      fontFamily: 'var(--font-mono)',
                    }}>
                      {r.severity === 'high' ? 'КРИТИЧНО' : 'СРЕДНИЙ'}
                    </span>
                  </div>
                  <div style={{ color: 'var(--color-smoke)', fontSize: '12px', fontWeight: 400 }}>{r.description}</div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Team Activity */}
        <div style={{
          background: 'transparent',
          border: '1px solid var(--color-graphite)',
          borderRadius: 0,
          padding: '24px',
          display: 'flex',
          flexDirection: 'column'
        }}>
          <h3 style={{ fontSize: '16px', fontWeight: 400, color: 'var(--color-chalk)', margin: '0 0 24px 0', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Users size={18} color="var(--color-compass-gold)" />
            Активность базы знаний
          </h3>
          
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            {[
              { name: 'Общий размер чанков текста', val: stats.chunks, desc: 'Объем проиндексированных блоков знаний' },
              { name: 'Всего связей фактов (edges)', val: stats.relations, desc: 'Количество утверждений в графе' },
              { name: 'Плотность графа знаний', val: stats.entities > 0 ? (stats.relations / stats.entities).toFixed(2) : '0.00', desc: 'Среднее число связей на одну сущность' },
            ].map((t, i) => (
              <div key={i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '12px', background: 'transparent', borderRadius: 0, border: '1px solid var(--color-graphite)' }}>
                <div>
                  <div style={{ color: 'var(--color-chalk)', fontSize: '14px', fontWeight: 400, marginBottom: '2px' }}>{t.name}</div>
                  <div style={{ color: 'var(--color-smoke)', fontSize: '12px' }}>{t.desc}</div>
                </div>
                <span style={{ fontSize: '16px', color: 'var(--color-compass-gold)', fontWeight: 400, fontFamily: 'var(--font-mono)' }}>{t.val}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
