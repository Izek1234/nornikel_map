'use client'

import { useState, useEffect, useCallback, useRef } from 'react'
import { Bell, BellOff, Check, Trash2, X, Settings, Mail } from 'lucide-react'
import { fetcher } from '@/lib/api'
import { useAuth } from './auth-provider'

type Notification = {
  id: string
  type: string
  title: string
  body: string
  link: string
  read: boolean
  created_at: number
}

const TYPE_LABELS: Record<string, string> = {
  new_document: '📄 Новый документ',
  document_processed: '✅ Документ обработан',
  new_experiment: '🧪 Новый эксперимент',
  domain_update: '🔄 Обновление домена',
  system: '⚙️ Система',
}

function timeAgo(ts: number): string {
  const diff = Date.now() / 1000 - ts
  if (diff < 60) return 'только что'
  if (diff < 3600) return `${Math.floor(diff / 60)} мин назад`
  if (diff < 86400) return `${Math.floor(diff / 3600)} ч назад`
  return `${Math.floor(diff / 86400)} дн назад`
}

export function NotificationBell() {
  const { token } = useAuth()
  const [open, setOpen] = useState(false)
  const [notifications, setNotifications] = useState<Notification[]>([])
  const [unreadCount, setUnreadCount] = useState(0)
  const [loading, setLoading] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  const headers: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {}

  const fetchNotifications = useCallback(async () => {
    try {
      const [notifs, count] = await Promise.all([
        fetcher<{ notifications: Notification[] }>('/api/notifications?limit=20'),
        fetcher<{ count: number }>('/api/notifications/unread-count'),
      ])
      setNotifications(notifs.notifications || [])
      setUnreadCount(count.count || 0)
    } catch {}
  }, [])

  useEffect(() => {
    if (token) fetchNotifications()
    const interval = setInterval(() => { if (token) fetchNotifications() }, 30000)
    return () => clearInterval(interval)
  }, [token, fetchNotifications])

  // Close on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    if (open) document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [open])

  async function markAllRead() {
    await fetch('/api/notifications/read', { method: 'POST', headers })
    fetchNotifications()
  }

  async function markRead(id: string) {
    await fetch(`/api/notifications/read?notification_id=${id}`, { method: 'POST', headers })
    fetchNotifications()
  }

  async function removeNotif(id: string) {
    await fetch(`/api/notifications/${id}`, { method: 'DELETE', headers })
    fetchNotifications()
  }

  return (
    <div ref={ref} style={{ position: 'relative' }}>
      <button
        type="button"
        onClick={() => {
          if (!token) return
          setOpen(!open)
          if (!open) fetchNotifications()
        }}
        style={{
          background: 'transparent', border: 'none', color: token ? 'var(--color-smoke)' : 'var(--color-graphite)',
          cursor: token ? 'pointer' : 'default', padding: '4px', position: 'relative', display: 'flex',
          alignItems: 'center', justifyContent: 'center', opacity: token ? 1 : 0.4,
        }}
        onMouseEnter={e => e.currentTarget.style.color = '#ffffff'}
        onMouseLeave={e => e.currentTarget.style.color = 'var(--color-smoke)'}
        title="Уведомления"
      >
        <Bell size={16} />
        {unreadCount > 0 && (
          <span style={{
            position: 'absolute', top: '-2px', right: '-2px',
            background: '#ef4444', color: '#ffffff',
            fontSize: '9px', fontWeight: 600, fontFamily: 'var(--font-mono)',
            minWidth: '14px', height: '14px', borderRadius: '7px',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            padding: '0 3px',
          }}>
            {unreadCount > 99 ? '99+' : unreadCount}
          </span>
        )}
      </button>

      {open && token && (
        <div style={{
          position: 'absolute', top: '100%', right: 0, marginTop: '8px',
          width: '360px', maxHeight: '480px', overflow: 'hidden',
          background: 'var(--color-obsidian)', border: '1px solid var(--color-graphite)',
          borderRadius: 0, zIndex: 100, display: 'flex', flexDirection: 'column',
        }}>
          {/* Header */}
          <div style={{
            padding: '14px 16px', borderBottom: '1px solid var(--color-graphite)',
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          }}>
            <span style={{
              fontFamily: 'var(--font-aeonik)', fontSize: '13px', fontWeight: 500,
              color: 'var(--color-chalk)',
            }}>
              Уведомления {unreadCount > 0 && <span style={{ color: 'var(--color-smoke)' }}>({unreadCount})</span>}
            </span>
            <div style={{ display: 'flex', gap: '8px' }}>
              {unreadCount > 0 && (
                <button onClick={markAllRead} style={{
                  background: 'transparent', border: 'none', color: 'var(--color-smoke)',
                  cursor: 'pointer', padding: '2px', display: 'flex',
                }} title="Отметить все как прочитанные">
                  <Check size={14} />
                </button>
              )}
              <button onClick={() => setOpen(false)} style={{
                background: 'transparent', border: 'none', color: 'var(--color-smoke)',
                cursor: 'pointer', padding: '2px', display: 'flex',
              }}>
                <X size={14} />
              </button>
            </div>
          </div>

          {/* List */}
          <div style={{ overflowY: 'auto', flex: 1 }}>
            {notifications.length === 0 ? (
              <div style={{
                padding: '32px 16px', textAlign: 'center',
                color: 'var(--color-smoke)', fontSize: '13px',
              }}>
                <BellOff size={24} style={{ marginBottom: '8px', opacity: 0.4 }} />
                <p style={{ margin: 0 }}>Нет уведомлений</p>
              </div>
            ) : (
              notifications.map(n => (
                <div
                  key={n.id}
                  style={{
                    padding: '12px 16px', borderBottom: '1px solid var(--color-graphite)',
                    background: n.read ? 'transparent' : 'rgba(152, 255, 56, 0.03)',
                    cursor: 'pointer', transition: 'background 0.15s',
                  }}
                  onMouseEnter={e => e.currentTarget.style.background = 'rgba(255,255,255,0.02)'}
                  onMouseLeave={e => e.currentTarget.style.background = n.read ? 'transparent' : 'rgba(152, 255, 56, 0.03)'}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '4px' }}>
                        {!n.read && <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#98ff38', flexShrink: 0 }} />}
                        <span style={{
                          fontFamily: 'var(--font-mono)', fontSize: '11px',
                          color: 'var(--color-smoke)',
                        }}>
                          {TYPE_LABELS[n.type] || n.type}
                        </span>
                      </div>
                      <p style={{
                        fontFamily: 'var(--font-aeonik)', fontSize: '13px',
                        color: 'var(--color-chalk)', margin: 0, lineHeight: 1.4,
                      }}>{n.title}</p>
                      {n.body && (
                        <p style={{
                          fontFamily: 'var(--font-aeonik)', fontSize: '12px',
                          color: 'var(--color-smoke)', margin: '4px 0 0 0', lineHeight: 1.4,
                        }}>{n.body.length > 100 ? n.body.slice(0, 100) + '...' : n.body}</p>
                      )}
                      <span style={{
                        fontFamily: 'var(--font-mono)', fontSize: '10px',
                        color: 'var(--color-graphite)',
                      }}>{timeAgo(n.created_at)}</span>
                    </div>
                    <div style={{ display: 'flex', gap: '4px', flexShrink: 0, marginLeft: '8px' }}>
                      {!n.read && (
                        <button onClick={(e) => { e.stopPropagation(); markRead(n.id) }} style={{
                          background: 'transparent', border: 'none', color: 'var(--color-smoke)',
                          cursor: 'pointer', padding: '2px', display: 'flex',
                        }} title="Прочитано">
                          <Check size={12} />
                        </button>
                      )}
                      <button onClick={(e) => { e.stopPropagation(); removeNotif(n.id) }} style={{
                        background: 'transparent', border: 'none', color: 'var(--color-smoke)',
                        cursor: 'pointer', padding: '2px', display: 'flex',
                      }} title="Удалить">
                        <Trash2 size={12} />
                      </button>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  )
}
