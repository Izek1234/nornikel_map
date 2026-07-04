import { useState, useRef, useEffect } from 'react'

type Option = {
  id: string
  label: string
}

export function CustomSelect({
  options,
  value,
  onChange,
  placeholder = 'Select...',
  direction = 'down',
}: {
  options: Option[]
  value: string
  onChange: (id: string) => void
  placeholder?: string
  direction?: 'up' | 'down'
}) {
  const [isOpen, setIsOpen] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false)
      }
    }
    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside)
    }
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [isOpen])

  const selectedOption = options.find((o) => o.id === value)

  return (
    <div ref={containerRef} style={{ position: 'relative', display: 'inline-block' }}>
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '8px',
          background: 'var(--color-obsidian)',
          border: `1px solid ${isOpen ? 'var(--color-graphite)' : 'var(--color-graphite)'}`,
          borderRadius: 0,
          padding: '6px 12px',
          color: '#ffffff',
          fontFamily: "var(--font-aeonik)",
          fontSize: '13px',
          cursor: 'pointer',
          minWidth: '140px',
          transition: 'all 0.2s',
          boxShadow: 'none',
        }}
        onMouseEnter={(e) => {
          if (!isOpen) e.currentTarget.style.borderColor = 'var(--color-graphite)'
        }}
        onMouseLeave={(e) => {
          if (!isOpen) e.currentTarget.style.borderColor = 'var(--color-graphite)'
        }}
      >
        <span>{selectedOption ? selectedOption.label : placeholder}</span>
        <svg
          width="10"
          height="6"
          viewBox="0 0 10 6"
          fill="none"
          style={{
            transform: isOpen 
              ? (direction === 'up' ? 'rotate(0deg)' : 'rotate(180deg)') 
              : (direction === 'up' ? 'rotate(180deg)' : 'rotate(0deg)'),
            transition: 'transform 0.2s',
          }}
        >
          <path
            d="M1 1L5 5L9 1"
            stroke="var(--color-smoke)"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </button>

      {isOpen && (
        <div
          className="animate-fade-in-scale"
          style={{
            position: 'absolute',
            bottom: direction === 'up' ? 'calc(100% + 4px)' : 'auto',
            top: direction === 'down' ? 'calc(100% + 4px)' : 'auto',
            left: 0,
            width: '100%',
            minWidth: 'max-content',
            background: 'var(--color-obsidian)',
            border: '1px solid var(--color-graphite)',
            borderRadius: 0,
            boxShadow: '0 8px 16px rgba(0,0,0,0.5)',
            zIndex: 100,
            maxHeight: '200px',
            overflowY: 'auto',
            padding: '6px',
            display: 'flex',
            flexDirection: 'column',
            gap: '4px',
          }}
        >
          {options.map((opt) => {
            const isActive = value === opt.id
            return (
              <button
                key={opt.id}
                type="button"
                onClick={() => {
                  onChange(opt.id)
                  setIsOpen(false)
                }}
                style={{
                  background: isActive ? 'var(--color-graphite)' : 'transparent',
                  color: isActive ? '#ffffff' : 'var(--color-chalk)',
                  border: 'none',
                  borderRadius: 0,
                  padding: '8px 12px',
                  textAlign: 'left',
                  fontFamily: "var(--font-aeonik)",
                  fontSize: '13px',
                  cursor: 'pointer',
                  transition: 'background 0.1s',
                }}
                onMouseEnter={(e) => {
                  if (!isActive) {
                    e.currentTarget.style.background = 'transparent'
                    e.currentTarget.style.color = '#ffffff'
                  }
                }}
                onMouseLeave={(e) => {
                  if (!isActive) {
                    e.currentTarget.style.background = 'transparent'
                    e.currentTarget.style.color = 'var(--color-chalk)'
                  }
                }}
              >
                {opt.label}
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}
