'use client'

import useSWR from 'swr'
import { Database, HardDrive, LogOut, User } from 'lucide-react'
import { fetcher, type Health, type Stats } from '@/lib/api'
import { ThemeToggle } from '@/components/theme-toggle'
import { useAuth } from '@/components/auth-provider'
import { NotificationBell } from '@/components/notifications'
import { NotificationSettings } from '@/components/notification-settings'

/* ── Status badge ── */
function StatusDot({ ok, label }: { ok: boolean; label: string }) {
  return (
    <span style={{ 
      display: 'flex', alignItems: 'center', gap: '6px',
      color: ok ? 'var(--color-smoke)' : '#ef4444', 
      fontSize: '12px', fontFamily: "var(--font-mono)",
      fontWeight: 400, textTransform: 'uppercase', letterSpacing: '0.5px'
    }}>
      <span style={{
        width: '6px', height: '6px', borderRadius: '50%',
        background: ok ? '#98ff38' : '#ef4444',
        boxShadow: ok ? '0 0 8px rgba(152, 255, 56, 0.4)' : 'none'
      }} aria-hidden="true" />
      {label}
    </span>
  )
}

function StatBadge({ value, label }: { value?: number; label: string }) {
  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      gap: '6px',
    }}>
      <span style={{
        fontFamily: "var(--font-mono)",
        fontSize: '12px',
        fontWeight: 400,
        color: 'var(--color-smoke)',
        textTransform: 'uppercase'
      }}>{label}:</span>
      <span style={{
        fontFamily: "var(--font-mono)",
        fontSize: '12px',
        fontWeight: 400,
        color: 'var(--color-chalk)',
      }}>{(value ?? 0).toLocaleString('ru')}</span>
    </div>
  )
}

export function AppHeader({
  currentTab,
  onTabChange,
  tabs
}: {
  currentTab?: string;
  onTabChange?: (id: string) => void;
  tabs?: readonly { id: string; label: string }[];
} = {}) {
  const { data: health } = useSWR<Health>('/api/health', fetcher, { refreshInterval: 30000 })
  const { data: statsData } = useSWR<Stats>('/api/stats', fetcher, { refreshInterval: 60000 })
  const { user, logout } = useAuth()
  
  const stats = statsData || { entities: 0, facts: 0, relations: 0 }
  const llmOk = !!health?.llm?.ok
  const llmLabel = health?.llm?.provider === 'ollama' ? 'Ollama' : 'YandexGPT'
  const neo4jOk = !!health?.neo4j

  return (
    <header style={{
      background: 'transparent',
      borderBottom: '1px solid var(--color-graphite)',
      position: 'sticky',
      top: 0,
      zIndex: 50,
      padding: '8px 0'
    }}>
      <div style={{
        width: '100%',
        maxWidth: 'none',
        padding: '0 32px',
        height: '32px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
      }}>
        {/* Logo */}
        <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px', cursor: 'default' }}>
          <h1 style={{
            fontFamily: "var(--font-aeonik)",
            fontSize: '18px',
            fontWeight: 400,
            color: 'var(--color-chalk)',
            margin: 0,
          }}>
            Норникель
          </h1>
          <p style={{
            fontFamily: "var(--font-mono)",
            fontSize: '13px',
            color: 'var(--color-smoke)',
            margin: 0,
            textTransform: 'uppercase'
          }}>
            Карта знаний
          </p>
        </div>

        {/* Center - Tabs */}
        {tabs && currentTab && onTabChange && (
          <div style={{ display: 'flex', gap: '40px', alignItems: 'center' }}>
            {tabs.map((t) => {
              const isActive = currentTab === t.id
              return (
                <button
                  key={t.id}
                  type="button"
                  className="shimmer-tab"
                  onClick={() => onTabChange(t.id)}
                  aria-current={isActive ? 'page' : undefined}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px',
                    fontFamily: "var(--font-mono)",
                    fontSize: '13px',
                    fontWeight: 400,
                    textTransform: 'uppercase',
                    color: isActive ? 'var(--color-chalk)' : 'var(--color-smoke)',
                    background: 'transparent',
                    border: 'none',
                    cursor: 'pointer',
                    transition: 'all 0.15s ease',
                    outline: 'none',
                  }}
                >
                  {t.label}
                </button>
              )
            })}
          </div>
        )}

        {/* Right side */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '24px' }}>
          {/* Stats removed */}

          {/* Status dots */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
            <StatusDot ok={llmOk} label={llmLabel} />
            <StatusDot ok={neo4jOk} label="Neo4j" />
          </div>

          {/* Notifications */}
          {user && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <NotificationSettings />
              <NotificationBell />
            </div>
          )}

          {/* User info */}
          {user && (
            <>
              <div style={{ width: '1px', height: '16px', background: 'var(--color-graphite)' }} />
              <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <User size={14} color="var(--color-smoke)" />
                  <span style={{
                    fontFamily: "var(--font-mono)", fontSize: '12px',
                    color: 'var(--color-chalk)', textTransform: 'uppercase',
                  }}>
                    {user.display_name || user.username}
                  </span>
                  <span style={{
                    fontFamily: "var(--font-mono)", fontSize: '10px',
                    color: 'var(--color-smoke)', padding: '2px 6px',
                    border: '1px solid var(--color-graphite)',
                  }}>
                    {user.role}
                  </span>
                  <button
                    type="button"
                    onClick={logout}
                    title="Выйти"
                    style={{
                      background: 'transparent', border: 'none',
                      color: 'var(--color-smoke)', cursor: 'pointer',
                      padding: '4px', display: 'flex', alignItems: 'center',
                      transition: 'color 0.2s',
                    }}
                    onMouseEnter={e => e.currentTarget.style.color = '#ef4444'}
                    onMouseLeave={e => e.currentTarget.style.color = 'var(--color-smoke)'}
                  >
                    <LogOut size={14} />
                  </button>
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </header>
  )
}
