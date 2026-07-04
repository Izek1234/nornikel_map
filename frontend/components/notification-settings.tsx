'use client'

import { useState, useEffect } from 'react'
import { Settings, Plus, Trash2, Mail } from 'lucide-react'
import { fetcher, type Domain } from '@/lib/api'
import { useAuth } from './auth-provider'

type Subscription = {
  id: string
  domain: string
  email: string
  created_at: number
}

export function NotificationSettings() {
  const { token } = useAuth()
  const [subs, setSubs] = useState<Subscription[]>([])
  const [domains, setDomains] = useState<Domain[]>([])
  const [domain, setDomain] = useState('all')
  const [email, setEmail] = useState('')
  const [loading, setLoading] = useState(false)
  const [open, setOpen] = useState(false)

  const headers = { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) }

  useEffect(() => {
    if (open && token) {
      Promise.all([
        fetcher<{ subscriptions: Subscription[] }>('/api/subscriptions'),
        fetcher<{ domains: Domain[] }>('/api/domains'),
      ]).then(([s, d]) => {
        setSubs(s.subscriptions || [])
        setDomains(d.domains || [])
      }).catch(() => {})
    }
  }, [open, token])

  async function addSub() {
    setLoading(true)
    try {
      const params = new URLSearchParams()
      if (domain !== 'all') params.set('domain', domain)
      if (email) params.set('email', email)
      const res = await fetch(`/api/subscriptions?${params}`, { method: 'POST', headers })
      if (res.ok) {
        const sub = await res.json()
        setSubs(prev => [sub, ...prev])
        setDomain('all')
        setEmail('')
      }
    } finally { setLoading(false) }
  }

  async function removeSub(id: string) {
    await fetch(`/api/subscriptions/${id}`, { method: 'DELETE', headers })
    setSubs(prev => prev.filter(s => s.id !== id))
  }

  if (!token) return null

  return (
    <div style={{ position: 'relative' }}>
      <button
        type="button"
        onClick={() => setOpen(!open)}
        title="Настройки уведомлений"
        style={{
          background: 'transparent', border: 'none', color: 'var(--color-smoke)',
          cursor: 'pointer', padding: '4px', display: 'flex', alignItems: 'center',
        }}
        onMouseEnter={e => e.currentTarget.style.color = '#ffffff'}
        onMouseLeave={e => e.currentTarget.style.color = 'var(--color-smoke)'}
      >
        <Settings size={14} />
      </button>

      {open && (
        <div style={{
          position: 'fixed', inset: 0, zIndex: 200,
          background: 'rgba(0,0,0,0.5)', display: 'flex',
          alignItems: 'center', justifyContent: 'center',
        }} onClick={() => setOpen(false)}>
          <div
            onClick={e => e.stopPropagation()}
            style={{
              width: '440px', maxHeight: '80vh', overflow: 'auto',
              background: 'var(--color-obsidian)', border: '1px solid var(--color-graphite)',
              borderRadius: 0, padding: '24px',
            }}
          >
            <h3 style={{
              fontFamily: 'var(--font-aeonik)', fontSize: '16px', fontWeight: 400,
              color: 'var(--color-chalk)', margin: '0 0 20px 0',
            }}>Подписки на уведомления</h3>

            {/* Add subscription form */}
            <div style={{
              display: 'flex', flexDirection: 'column', gap: '10px',
              padding: '16px', border: '1px solid var(--color-graphite)',
              marginBottom: '16px',
            }}>
              <div>
                <label style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', color: 'var(--color-smoke)', display: 'block', marginBottom: '4px' }}>
                  ДОМЕН
                </label>
                <select
                  value={domain}
                  onChange={e => setDomain(e.target.value)}
                  style={{
                    width: '100%', padding: '8px 10px',
                    background: 'var(--control-bg)', border: '1px solid var(--control-border)',
                    color: 'var(--control-text)', fontFamily: 'var(--font-helvetica-now-text)',
                    fontSize: '13px', borderRadius: 0,
                  }}
                >
                  <option value="all">Все домены</option>
                  {domains.map(d => <option key={d.id} value={d.id}>{d.name_ru}</option>)}
                </select>
              </div>
              <div>
                <label style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', color: 'var(--color-smoke)', display: 'block', marginBottom: '4px' }}>
                  <Mail size={10} style={{ display: 'inline', marginRight: '4px' }} /> EMAIL (для почтовых уведомлений)
                </label>
                <input
                  type="email"
                  value={email}
                  onChange={e => setEmail(e.target.value)}
                  placeholder="user@example.com"
                  style={{
                    width: '100%', padding: '8px 10px',
                    background: 'var(--control-bg)', border: '1px solid var(--control-border)',
                    color: 'var(--control-text)', fontFamily: 'var(--font-helvetica-now-text)',
                    fontSize: '13px', borderRadius: 0, boxSizing: 'border-box',
                  }}
                />
              </div>
              <button
                onClick={addSub}
                disabled={loading}
                style={{
                  padding: '8px 16px', background: '#ffffff', color: '#000000',
                  border: '1px solid #ffffff', borderRadius: 0, cursor: 'pointer',
                  fontFamily: 'var(--font-helvetica-now-text)', fontSize: '13px',
                  display: 'flex', alignItems: 'center', gap: '6px', justifyContent: 'center',
                }}
              >
                <Plus size={14} />
                {loading ? 'Добавление...' : 'Подписаться'}
              </button>
            </div>

            {/* Existing subscriptions */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              {subs.length === 0 ? (
                <p style={{ fontFamily: 'var(--font-aeonik)', fontSize: '13px', color: 'var(--color-smoke)', textAlign: 'center', padding: '16px', margin: 0 }}>
                  Нет подписок
                </p>
              ) : (
                subs.map(s => {
                  const domLabel = s.domain === 'all' ? 'Все домены' : domains.find(d => d.id === s.domain)?.name_ru || s.domain
                  return (
                    <div key={s.id} style={{
                      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                      padding: '10px 12px', border: '1px solid var(--color-graphite)',
                    }}>
                      <div>
                        <span style={{ fontFamily: 'var(--font-aeonik)', fontSize: '13px', color: 'var(--color-chalk)' }}>
                          {domLabel}
                        </span>
                        {s.email && (
                          <span style={{
                            fontFamily: 'var(--font-mono)', fontSize: '11px',
                            color: 'var(--color-smoke)', marginLeft: '8px',
                          }}>
                            → {s.email}
                          </span>
                        )}
                      </div>
                      <button
                        onClick={() => removeSub(s.id)}
                        style={{
                          background: 'transparent', border: 'none', color: 'var(--color-smoke)',
                          cursor: 'pointer', padding: '4px', display: 'flex',
                        }}
                        onMouseEnter={e => e.currentTarget.style.color = '#ef4444'}
                        onMouseLeave={e => e.currentTarget.style.color = 'var(--color-smoke)'}
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  )
                })
              )}
            </div>

            <button
              onClick={() => setOpen(false)}
              style={{
                width: '100%', marginTop: '16px', padding: '10px',
                background: 'transparent', border: '1px solid var(--color-graphite)',
                color: 'var(--color-smoke)', cursor: 'pointer',
                fontFamily: 'var(--font-helvetica-now-text)', fontSize: '13px',
              }}
            >
              Закрыть
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
