'use client'

import { useState } from 'react'
import { Files, Menu, MessageCircle, Network, Plus, Search, Shield } from 'lucide-react'
import { AppHeader } from '@/components/app-header'
import { DashboardsTab } from '@/components/dashboards-tab'
import { DocumentsTab } from '@/components/documents-tab'
import { ChatTab } from '@/components/chat-tab'
import { GraphTab } from '@/components/graph-tab'
import { AuditTab } from '@/components/audit-tab'
import { useTheme } from '@/components/theme-provider'
import { useAuth } from '@/components/auth-provider'
import { AuthForm } from '@/components/auth-form'

const TABS = [
  { id: 'dashboards', label: 'Дашборды' },
  { id: 'documents', label: 'Документы' },
  { id: 'chat', label: 'AI Чат' },
  { id: 'graph', label: 'Нейро-Граф' },
  { id: 'audit', label: 'Аудит' },
] as const

type TabId = (typeof TABS)[number]['id']

export default function HomePage() {
  const [tab, setTab] = useState<TabId>('dashboards')
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const { theme } = useTheme()
  const { user, isLoading } = useAuth()

  if (isLoading) {
    return (
      <div style={{ minHeight: '100dvh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'var(--color-obsidian)' }}>
        <p style={{ fontFamily: "var(--font-mono)", fontSize: '13px', color: 'var(--color-smoke)' }}>Загрузка...</p>
      </div>
    )
  }

  if (!user) return <AuthForm />

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100dvh', overflow: 'hidden', background: 'var(--color-obsidian)' }}>
      <AppHeader currentTab={tab} onTabChange={(id) => setTab(id as TabId)} tabs={TABS} />

      {/* Main Content — full width */}
      <main style={{
        flex: 1,
        overflowY: tab === 'graph' || tab === 'chat' ? 'hidden' : 'auto',
        overflowX: 'hidden',
        width: '100%',
        position: 'relative',
        background: 'transparent',
        ...(tab === 'graph' || tab === 'chat' ? {} : { padding: '40px 32px' }),
      }}>
        <div style={{ position: 'relative', zIndex: 1, height: '100%', maxWidth: 'none' }}>
          {tab === 'dashboards' && <div className="animate-slide-up"><DashboardsTab /></div>}
          {tab === 'documents' && <div className="animate-slide-up"><DocumentsTab /></div>}
          {tab === 'chat' && <div className="animate-slide-up" style={{ height: '100%' }}><ChatTab /></div>}
          {tab === 'graph' && <div className="animate-slide-up" style={{ height: '100%' }}><GraphTab /></div>}
          {tab === 'audit' && <div className="animate-slide-up"><AuditTab /></div>}
        </div>
      </main>
    </div>
  )
}
