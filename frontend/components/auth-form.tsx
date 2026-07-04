'use client'

import { useState, type FormEvent } from 'react'
import { useAuth } from './auth-provider'

const ROLES = [
  { value: 'researcher', label: 'Исследователь' },
  { value: 'analyst', label: 'Аналитик' },
  { value: 'project_manager', label: 'Руководитель' },
]

const inputStyle = {
  width: '100%',
  padding: '12px 14px',
  background: 'var(--control-bg)',
  border: '1px solid var(--control-border)',
  borderRadius: 0,
  color: 'var(--control-text)',
  fontFamily: "var(--font-helvetica-now-text)",
  fontSize: '14px',
  outline: 'none',
  transition: 'border-color 0.2s',
  boxSizing: 'border-box' as const,
}

const btnPrimary = {
  width: '100%',
  padding: '12px',
  background: '#ffffff',
  border: '1px solid #ffffff',
  borderRadius: 0,
  color: '#000000',
  fontFamily: "var(--font-helvetica-now-text)",
  fontSize: '14px',
  fontWeight: 500,
  cursor: 'pointer',
  transition: 'all 0.2s',
}

const btnSecondary = {
  width: '100%',
  padding: '12px',
  background: 'transparent',
  border: '1px solid var(--control-border)',
  borderRadius: 0,
  color: 'var(--control-text)',
  fontFamily: "var(--font-helvetica-now-text)",
  fontSize: '14px',
  fontWeight: 400,
  cursor: 'pointer',
  transition: 'all 0.2s',
}

export function AuthForm() {
  const { login, register } = useAuth()
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [role, setRole] = useState('researcher')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError('')
    if (!username.trim() || !password.trim()) {
      setError('Заполните все поля')
      return
    }
    setLoading(true)
    try {
      if (mode === 'login') {
        const err = await login(username.trim(), password)
        if (err) setError(err)
      } else {
        const err = await register(username.trim(), password, role, displayName.trim())
        if (err) setError(err)
      }
    } catch {
      setError('Сетевая ошибка')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{
      minHeight: '100dvh',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      background: 'var(--color-obsidian)',
      padding: '20px',
    }}>
      <div style={{
        width: '100%',
        maxWidth: '380px',
        background: 'transparent',
        border: '1px solid var(--color-graphite)',
        borderRadius: 0,
        padding: '40px 32px',
      }}>
        {/* Logo */}
        <div style={{ textAlign: 'center', marginBottom: '32px' }}>
          <h1 style={{
            fontFamily: "var(--font-aeonik)",
            fontSize: '22px',
            fontWeight: 400,
            color: 'var(--color-chalk)',
            margin: '0 0 4px 0',
          }}>
            Норникель
          </h1>
          <p style={{
            fontFamily: "var(--font-mono)",
            fontSize: '12px',
            color: 'var(--color-smoke)',
            margin: 0,
            textTransform: 'uppercase',
            letterSpacing: '0.1em',
          }}>
            Карта знаний R&D
          </p>
        </div>

        {/* Tabs */}
        <div style={{ display: 'flex', marginBottom: '24px', border: '1px solid var(--control-border)' }}>
          {(['login', 'register'] as const).map(m => (
            <button
              key={m}
              type="button"
              onClick={() => { setMode(m); setError('') }}
              style={{
                flex: 1,
                padding: '10px',
                background: mode === m ? 'var(--control-bg)' : 'transparent',
                border: 'none',
                borderBottom: mode === m ? '2px solid var(--color-chalk)' : '2px solid transparent',
                color: mode === m ? 'var(--color-chalk)' : 'var(--color-smoke)',
                fontFamily: "var(--font-helvetica-now-text)",
                fontSize: '13px',
                cursor: 'pointer',
                transition: 'all 0.15s',
              }}
            >
              {m === 'login' ? 'Вход' : 'Регистрация'}
            </button>
          ))}
        </div>

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
          {mode === 'register' && (
            <>
              <div>
                <label style={{ fontFamily: "var(--font-helvetica-now-text)", fontSize: '12px', color: 'var(--color-smoke)', display: 'block', marginBottom: '6px' }}>
                  Отображаемое имя
                </label>
                <input
                  type="text"
                  value={displayName}
                  onChange={e => setDisplayName(e.target.value)}
                  placeholder="Иван Иванов"
                  style={inputStyle}
                  onFocus={e => e.currentTarget.style.borderColor = 'var(--color-chalk)'}
                  onBlur={e => e.currentTarget.style.borderColor = 'var(--control-border)'}
                />
              </div>
              <div>
                <label style={{ fontFamily: "var(--font-helvetica-now-text)", fontSize: '12px', color: 'var(--color-smoke)', display: 'block', marginBottom: '6px' }}>
                  Роль
                </label>
                <select
                  value={role}
                  onChange={e => setRole(e.target.value)}
                  style={{ ...inputStyle, cursor: 'pointer' }}
                >
                  {ROLES.map(r => <option key={r.value} value={r.value}>{r.label}</option>)}
                </select>
              </div>
            </>
          )}

          <div>
            <label style={{ fontFamily: "var(--font-helvetica-now-text)", fontSize: '12px', color: 'var(--color-smoke)', display: 'block', marginBottom: '6px' }}>
              Логин
            </label>
            <input
              type="text"
              value={username}
              onChange={e => setUsername(e.target.value)}
              placeholder="username"
              autoComplete="username"
              style={inputStyle}
              onFocus={e => e.currentTarget.style.borderColor = 'var(--color-chalk)'}
              onBlur={e => e.currentTarget.style.borderColor = 'var(--control-border)'}
            />
          </div>

          <div>
            <label style={{ fontFamily: "var(--font-helvetica-now-text)", fontSize: '12px', color: 'var(--color-smoke)', display: 'block', marginBottom: '6px' }}>
              Пароль
            </label>
            <input
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              placeholder="••••••••"
              autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
              style={inputStyle}
              onFocus={e => e.currentTarget.style.borderColor = 'var(--color-chalk)'}
              onBlur={e => e.currentTarget.style.borderColor = 'var(--control-border)'}
            />
          </div>

          {error && (
            <p style={{
              fontFamily: "var(--font-helvetica-now-text)",
              fontSize: '13px',
              color: '#ef4444',
              margin: 0,
              padding: '8px 12px',
              background: 'rgba(239, 68, 68, 0.08)',
              border: '1px solid rgba(239, 68, 68, 0.2)',
            }}>
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={loading}
            style={{
              ...(mode === 'login' ? btnPrimary : btnSecondary),
              opacity: loading ? 0.6 : 1,
              marginTop: '4px',
            }}
            onMouseEnter={e => { if (!loading) e.currentTarget.style.opacity = '0.85' }}
            onMouseLeave={e => { if (!loading) e.currentTarget.style.opacity = '1' }}
          >
            {loading ? 'Загрузка...' : mode === 'login' ? 'Войти' : 'Зарегистрироваться'}
          </button>
        </form>

        <p style={{
          fontFamily: "var(--font-mono)",
          fontSize: '11px',
          color: 'var(--color-smoke)',
          textAlign: 'center',
          marginTop: '20px',
          margin: '20px 0 0 0',
          opacity: 0.6,
        }}>
          {mode === 'login'
            ? 'Демо: admin / admin'
            : 'Доступ: researcher, analyst, project_manager'
          }
        </p>
      </div>
    </div>
  )
}
