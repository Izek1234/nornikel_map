'use client'

import { Moon, Sun } from 'lucide-react'
import { useTheme } from '@/components/theme-provider'

export function ThemeToggle() {
  const { theme, toggle } = useTheme()

  return (
    <button
      type="button"
      onClick={toggle}
      className="theme-toggle"
      title={theme === 'light' ? 'Переключить на тёмную тему' : 'Переключить на светлую тему'}
      aria-label={theme === 'light' ? 'Переключить на тёмную тему' : 'Переключить на светлую тему'}
    >
      {theme === 'light' ? <Moon size={15} /> : <Sun size={15} />}
    </button>
  )
}
