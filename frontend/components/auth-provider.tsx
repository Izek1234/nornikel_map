'use client'

import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from 'react'

type User = {
  id: string
  username: string
  role: string
  display_name: string
}

type AuthCtx = {
  user: User | null
  token: string | null
  login: (username: string, password: string) => Promise<string | null>
  register: (username: string, password: string, role?: string, displayName?: string) => Promise<string | null>
  logout: () => void
  isLoading: boolean
}

const AuthContext = createContext<AuthCtx>({
  user: null, token: null,
  login: async () => null, register: async () => null,
  logout: () => {}, isLoading: true,
})

export function useAuth() { return useContext(AuthContext) }

function parseJwt(token: string): User | null {
  try {
    const payload = JSON.parse(atob(token.split('.')[1]))
    if (payload.exp && payload.exp * 1000 < Date.now()) return null
    return { id: payload.sub, username: payload.username, role: payload.role, display_name: payload.display_name }
  } catch { return null }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(null)
  const [user, setUser] = useState<User | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    const saved = localStorage.getItem('nornikel_token')
    if (saved) {
      const u = parseJwt(saved)
      if (u) { setToken(saved); setUser(u) }
      else localStorage.removeItem('nornikel_token')
    }
    setIsLoading(false)
  }, [])

  const login = useCallback(async (username: string, password: string): Promise<string | null> => {
    const res = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      return err.detail || 'Ошибка входа'
    }
    const data = await res.json()
    localStorage.setItem('nornikel_token', data.token)
    setToken(data.token)
    setUser(data.user)
    return null
  }, [])

  const register = useCallback(async (username: string, password: string, role = 'researcher', displayName = ''): Promise<string | null> => {
    const res = await fetch('/api/auth/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password, role, display_name: displayName }),
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      return err.detail || 'Ошибка регистрации'
    }
    // Auto-login after registration
    return login(username, password)
  }, [login])

  const logout = useCallback(() => {
    localStorage.removeItem('nornikel_token')
    setToken(null)
    setUser(null)
  }, [])

  return (
    <AuthContext.Provider value={{ user, token, login, register, logout, isLoading }}>
      {children}
    </AuthContext.Provider>
  )
}
