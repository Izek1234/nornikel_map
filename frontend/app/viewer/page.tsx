'use client'

import { Suspense, useEffect, useState } from 'react'
import { useSearchParams, useRouter } from 'next/navigation'
import {
  FileText,
  Search,
  ArrowLeft,
  Download,
  ExternalLink,
  ChevronRight
} from 'lucide-react'

function ViewerContent() {
  const searchParams = useSearchParams()
  const router = useRouter()
  const name = searchParams.get('name')

  const [content, setContent] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')

  // PPTX Presentation slide viewer state
  const [pptxTab, setPptxTab] = useState<'slides' | 'text'>('slides')
  const [currentSlide, setCurrentSlide] = useState(0)

  useEffect(() => {
    if (!name) {
      setError('Имя документа не указано')
      return
    }
    setLoading(true)
    setError(null)
    setContent(null)
    fetch(`/api/documents/${encodeURIComponent(name)}/content`)
      .then(res => {
        if (!res.ok) {
          throw new Error('Не удалось загрузить содержимое документа')
        }
        return res.json()
      })
      .then(data => {
        setContent(data.content || 'Документ пуст')
      })
      .catch(err => {
        setError(err.message || 'Ошибка при загрузке документа')
      })
      .finally(() => {
        setLoading(false)
      })
  }, [name])

  if (!name) {
    return (
      <div style={{ padding: '40px', color: '#ef4444', fontFamily: 'var(--font-mono)' }}>
        ОШИБКА: ИМЯ ДОКУМЕНТА НЕ УКАЗАНО
      </div>
    )
  }

  const rawLines = content ? content.split('\n') : []
  const stats = {
    lines: rawLines.length,
    words: content ? content.split(/\s+/).filter(Boolean).length : 0,
    chars: content ? content.length : 0,
  }

  // Detect file extension
  const lowercaseName = name.toLowerCase()
  const isPdf = lowercaseName.endsWith('.pdf')
  const isMd = lowercaseName.endsWith('.md')
  const isPptx = lowercaseName.endsWith('.pptx')
  const isDocx = lowercaseName.endsWith('.docx')

  // Get human readable type label
  let fileTypeLabel = 'ТЕКСТОВЫЙ ДОКУМЕНТ'
  if (isPdf) fileTypeLabel = 'ДОКУМЕНТ PDF'
  else if (isMd) fileTypeLabel = 'MARKDOWN ДОКУМЕНТ'
  else if (isPptx) fileTypeLabel = 'ПРЕЗЕНТАЦИЯ POWERPOINT'
  else if (isDocx) fileTypeLabel = 'ДОКУМЕНТ MS WORD'

  // Render highlighted search content
  const renderLineContent = (text: string) => {
    if (!searchQuery.trim()) return text
    const parts = text.split(new RegExp(`(${searchQuery.replace(/[-[\]{}()*+?.,\\^$|#\s]/g, '\\$&')})`, 'gi'))
    return parts.map((part, index) => 
      part.toLowerCase() === searchQuery.toLowerCase() ? (
        <span key={index} style={{ background: '#3df2b4', color: '#000000', fontWeight: 'bold', padding: '0 2px' }}>{part}</span>
      ) : part
    )
  }

  // PPTX dynamic slides parser
  const slidesList = (() => {
    if (!content) return []
    if (content.includes('=== SLIDE ===')) {
      return content.split('=== SLIDE ===').map(s => s.trim()).filter(Boolean)
    }
    // Fallback: split by double newlines or group chunks
    const blocks = content.split('\n\n').map(b => b.trim()).filter(Boolean)
    if (blocks.length > 0) return blocks
    return [content]
  })()

  // Make sure currentSlide is in range
  const safeCurrentSlide = Math.min(currentSlide, Math.max(0, slidesList.length - 1))

  // Slide content text renderer
  const renderSlideContent = (slideText: string) => {
    const lines = slideText.split('\n').map(l => l.trim()).filter(Boolean)
    if (lines.length === 0) return null

    const title = lines[0]
    const bodyLines = lines.slice(1)

    // Separate images, table rows vs bullet points
    const imageLines = bodyLines.filter(l => l.startsWith('[IMAGE:'))
    const tableRows = bodyLines.filter(l => l.includes('|'))
    const bulletRows = bodyLines.filter(l => !l.includes('|') && !l.startsWith('[IMAGE:'))

    return (
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        padding: '40px 48px',
        boxSizing: 'border-box',
        justifyContent: 'flex-start',
        position: 'relative',
      }}>
        {/* Grid pattern overlay */}
        <div style={{
          position: 'absolute',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundImage: 'radial-gradient(var(--color-graphite) 1px, transparent 1px)',
          backgroundSize: '24px 24px',
          opacity: 0.15,
          pointerEvents: 'none'
        }} />

        {/* Slide header */}
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          borderBottom: '1px solid rgba(255,255,255,0.08)',
          paddingBottom: '18px',
          marginBottom: '24px',
          zIndex: 10
        }}>
          <h2 style={{
            margin: 0,
            fontSize: '24px',
            fontWeight: 600,
            color: '#3df2b4', // Mint accent
            letterSpacing: '-0.02em',
            lineHeight: 1.2
          }}>
            {title}
          </h2>
          <span style={{
            fontFamily: 'var(--font-mono)',
            fontSize: '11px',
            color: 'var(--color-smoke)',
            padding: '3px 10px',
            background: 'rgba(255,255,255,0.02)',
            border: '1px solid rgba(255,255,255,0.08)'
          }}>
            СЛАЙД {safeCurrentSlide + 1}
          </span>
        </div>

        {/* Slide Body */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'center', gap: '20px', zIndex: 10 }}>
          {/* Images Grid */}
          {imageLines.length > 0 && (
            <div style={{
              display: 'flex',
              gap: '16px',
              justifyContent: 'center',
              alignItems: 'center',
              flexWrap: 'wrap',
              margin: '12px 0'
            }}>
              {imageLines.map((line, idx) => {
                const match = line.match(/\[IMAGE:\s*([^\]]+)\]/)
                if (!match) return null
                const imgUrl = match[1].trim()
                return (
                  <div key={idx} style={{
                    border: '1px solid var(--color-graphite)',
                    background: '#000000',
                    padding: '6px',
                    maxWidth: '360px',
                    maxHeight: '200px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    overflow: 'hidden'
                  }}>
                    <img 
                      src={imgUrl} 
                      alt="Иллюстрация слайда" 
                      style={{ 
                        maxWidth: '100%', 
                        maxHeight: '100%', 
                        objectFit: 'contain' 
                      }} 
                    />
                  </div>
                )
              })}
            </div>
          )}

          {/* Bullet points */}
          {bulletRows.length > 0 && (
            <ul style={{
              margin: 0,
              padding: 0,
              display: 'flex',
              flexDirection: 'column',
              gap: '12px',
              listStyle: 'none'
            }}>
              {bulletRows.map((line, idx) => (
                <li key={idx} style={{
                  fontSize: '15px',
                  lineHeight: 1.6,
                  color: 'var(--color-chalk)',
                  paddingLeft: '24px',
                  position: 'relative'
                }}>
                  <span style={{ position: 'absolute', left: 0, color: '#8B5CF6' }}>⨁</span>
                  {renderLineContent(line)}
                </li>
              ))}
            </ul>
          )}

          {/* Dynamic Table parsing */}
          {tableRows.length > 0 && (
            <div style={{ overflowX: 'auto', marginTop: '16px' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13.5px' }}>
                <tbody>
                  {tableRows.map((row, rIdx) => {
                    const cells = row.split('|').map(c => c.trim())
                    return (
                      <tr key={rIdx} style={{
                        borderBottom: '1px solid rgba(255,255,255,0.06)',
                        background: rIdx === 0 ? 'rgba(255,255,255,0.03)' : 'transparent'
                      }}>
                        {cells.map((cell, cIdx) => (
                          <td key={cIdx} style={{
                            padding: '10px 14px',
                            color: rIdx === 0 ? '#ffffff' : 'var(--color-ash)',
                            fontWeight: rIdx === 0 ? 600 : 400
                          }}>
                            {renderLineContent(cell)}
                          </td>
                        ))}
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Slide Footer */}
        <div style={{
          marginTop: 'auto',
          display: 'flex',
          justifyContent: 'space-between',
          fontSize: '10px',
          color: 'var(--color-iron)',
          fontFamily: 'var(--font-mono)',
          borderTop: '1px solid rgba(255,255,255,0.04)',
          paddingTop: '14px',
          zIndex: 10
        }}>
          <span>НОРНИКЕЛЬ ГМК • АНАЛИТИЧЕСКИЙ ОБЗОР</span>
          <span>КОНФИДЕНЦИАЛЬНО</span>
        </div>
      </div>
    )
  }

  // Markdown rendering helper
  const renderMarkdown = (text: string) => {
    const html = text
      .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
      .replace(/\*([^*]+)\*/g, '<em>$1</em>')
      .replace(/^### (.+)$/gm, '<h4 style="margin:16px 0 8px;color:var(--color-chalk);font-size:15px;font-weight:600">$1</h4>')
      .replace(/^## (.+)$/gm, '<h3 style="margin:20px 0 10px;color:#ffffff;font-size:17px;font-weight:600">$1</h3>')
      .replace(/^# (.+)$/gm, '<h2 style="margin:24px 0 12px;color:#ffffff;font-size:19px;font-weight:700">$1</h2>')
      .replace(/^• (.+)$/gm, '<li style="margin:4px 0;padding-left:14px;list-style-type:none;position:relative;"><span style="position:absolute;left:0;color:#8B5CF6">⨁</span>$1</li>')
      .replace(/^- (.+)$/gm, '<li style="margin:4px 0;padding-left:14px;list-style-type:none;position:relative;"><span style="position:absolute;left:0;color:#8B5CF6">⨁</span>$1</li>')
      .replace(/^(\d+)\. (.+)$/gm, '<li style="margin:4px 0;padding-left:14px;list-style-type:none;position:relative;"><span style="position:absolute;left:0;color:#8B5CF6;font-family:monospace;font-size:11px">${{index}}</span>$2</li>')
      .replace(/`([^`]+)`/g, '<code style="background:rgba(255,255,255,0.07);padding:2px 6px;border-radius:0;font-family:monospace;font-size:13px;color:#3df2b4">$1</code>')
      .replace(/\n\n/g, '</p><p style="margin:12px 0">')
      .replace(/\n/g, '<br>')

    return (
      <div
        style={{
          fontFamily: "var(--font-aeonik)",
          fontSize: '14.5px',
          lineHeight: 1.7,
          color: 'var(--color-chalk)',
        }}
        dangerouslySetInnerHTML={{ __html: `<p style="margin:0">${html}</p>` }}
      />
    )
  }

  return (
    <div style={{
      minHeight: '100vh',
      background: '#0B0B0F', // Stark Yandex Cup deep dark background
      color: 'var(--color-chalk)',
      display: 'flex',
      flexDirection: 'column',
      fontFamily: 'var(--font-aeonik)',
      position: 'relative',
      overflow: 'hidden'
    }}>
      {/* Cyber noise background glyphs */}
      <div style={{
        position: 'absolute',
        top: '10%',
        right: '10%',
        fontFamily: 'var(--font-mono)',
        fontSize: '140px',
        color: 'rgba(255, 255, 255, 0.006)',
        userSelect: 'none',
        pointerEvents: 'none',
        zIndex: 0
      }}>
        ø
      </div>
      <div style={{
        position: 'absolute',
        bottom: '15%',
        left: '8%',
        fontFamily: 'var(--font-mono)',
        fontSize: '180px',
        color: 'rgba(255, 255, 255, 0.006)',
        userSelect: 'none',
        pointerEvents: 'none',
        zIndex: 0
      }}>
        ⨁
      </div>
      <div style={{
        position: 'absolute',
        top: '60%',
        left: '25%',
        fontFamily: 'var(--font-mono)',
        fontSize: '80px',
        color: 'rgba(255, 255, 255, 0.004)',
        userSelect: 'none',
        pointerEvents: 'none',
        zIndex: 0
      }}>
        λ
      </div>

      {/* Top Header */}
      <header style={{
        background: 'var(--color-carbon)',
        borderBottom: '1px solid var(--color-graphite)',
        padding: '12px 32px',
        position: 'sticky',
        top: 0,
        zIndex: 50,
      }}>
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '16px'
        }}>
          {/* Back button & title */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
            <button
              onClick={() => window.close()}
              style={{
                background: 'none',
                border: 'none',
                color: 'var(--color-smoke)',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                fontFamily: 'var(--font-mono)',
                fontSize: '11px',
                padding: 0,
                outline: 'none',
                textTransform: 'uppercase'
              }}
              onMouseEnter={e => e.currentTarget.style.color = '#8B5CF6'}
              onMouseLeave={e => e.currentTarget.style.color = 'var(--color-smoke)'}
            >
              <ArrowLeft size={14} /> ЗАКРЫТЬ ВКЛАДКУ
            </button>
            <div style={{ width: '1px', height: '16px', background: 'var(--color-graphite)' }} />
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{
                fontFamily: 'var(--font-mono)',
                fontSize: '11px',
                padding: '2px 8px',
                background: 'rgba(255,255,255,0.02)',
                border: '1px solid var(--color-graphite)',
                color: '#8B5CF6',
                letterSpacing: '0.05em'
              }}>
                {fileTypeLabel}
              </span>
              <span style={{ fontSize: '14px', fontWeight: 500, color: 'var(--color-chalk)' }}>
                {name}
              </span>
            </div>
          </div>

          {/* Title tag: { NORNICKEL | DOCUMENT VIEWER } */}
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: '12px', color: 'var(--color-smoke)', userSelect: 'none' }}>
            {'{'} NORNICKEL | DOCUMENT VIEWER {'}'}
          </div>

          {/* Raw download or open */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
            <a
              href={`/api/documents/${encodeURIComponent(name)}/content`}
              target="_blank"
              style={{
                fontFamily: 'var(--font-mono)',
                fontSize: '11px',
                color: 'var(--color-smoke)',
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                textDecoration: 'none'
              }}
              onMouseEnter={e => e.currentTarget.style.color = '#3df2b4'}
              onMouseLeave={e => e.currentTarget.style.color = 'var(--color-smoke)'}
            >
              ОТКРЫТЬ RAW <ExternalLink size={12} />
            </a>
          </div>
        </div>
      </header>

      {/* Info Stats Bar */}
      {content && (
        <section style={{
          background: '#0B0B0F',
          borderBottom: '1px solid var(--color-graphite)',
          padding: '12px 32px',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '12px',
          zIndex: 10
        }}>
          {/* Stats block */}
          <div style={{ display: 'flex', gap: '32px', alignItems: 'baseline' }}>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: '6px' }}>
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: '10px', color: 'var(--color-smoke)' }}>СТРОК</span>
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: '18px', fontWeight: 'bold', color: '#ffffff' }}>{stats.lines.toLocaleString()}</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: '6px' }}>
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: '10px', color: 'var(--color-smoke)' }}>СЛОВ</span>
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: '18px', fontWeight: 'bold', color: '#ffffff' }}>{stats.words.toLocaleString()}</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: '6px' }}>
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: '10px', color: 'var(--color-smoke)' }}>СИМВОЛОВ</span>
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: '18px', fontWeight: 'bold', color: '#ffffff' }}>{stats.chars.toLocaleString()}</span>
            </div>
          </div>

          {/* Search bar */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            background: 'var(--color-carbon)',
            border: '1px solid var(--color-graphite)',
            padding: '6px 12px',
            width: '320px',
          }}>
            <Search size={14} color="var(--color-smoke)" style={{ marginRight: '8px' }} />
            <input
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              placeholder="Поиск по содержимому документа..."
              style={{
                flex: 1,
                background: 'none',
                border: 'none',
                color: 'var(--color-chalk)',
                fontSize: '12px',
                fontFamily: 'var(--font-mono)',
                outline: 'none',
              }}
            />
            {searchQuery && (
              <button
                onClick={() => setSearchQuery('')}
                style={{
                  background: 'none',
                  border: 'none',
                  color: 'var(--color-smoke)',
                  fontSize: '11px',
                  fontFamily: 'var(--font-mono)',
                  cursor: 'pointer',
                  padding: 0,
                  outline: 'none'
                }}
              >
                ОЧИСТИТЬ
              </button>
            )}
          </div>
        </section>
      )}

      {/* Main Container */}
      <main style={{
        flex: 1,
        padding: '32px',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        background: 'transparent',
        overflowY: 'auto',
        zIndex: 10
      }}>
        <div style={{ maxWidth: '960px', width: '100%' }}>
          {loading && (
            <div style={{
              fontFamily: 'var(--font-mono)',
              fontSize: '12px',
              color: 'var(--color-smoke)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '12px',
              padding: '80px 0'
            }}>
              <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#8B5CF6', animation: 'pulse 1.2s infinite ease-in-out' }} />
              ЧТЕНИЕ ДОКУМЕНТА ИЗ БАЗЫ ЗНАНИЙ...
            </div>
          )}

          {error && (
            <div style={{
              padding: '24px',
              border: '1px solid #ef4444',
              background: 'rgba(239, 68, 68, 0.02)',
              color: '#ef4444',
              fontFamily: 'var(--font-mono)',
              fontSize: '13px',
              marginTop: '40px'
            }}>
              ОШИБКА: {error}
            </div>
          )}

          {content !== null && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
              {/* PPTX Tab Switcher */}
              {isPptx && (
                <div style={{ display: 'flex', gap: '8px', borderBottom: '1px solid var(--color-graphite)', paddingBottom: '12px' }}>
                  <button
                    onClick={() => setPptxTab('slides')}
                    style={{
                      background: pptxTab === 'slides' ? 'rgba(255, 255, 255, 0.04)' : 'none',
                      border: `1px solid ${pptxTab === 'slides' ? '#8B5CF6' : 'var(--color-graphite)'}`,
                      color: pptxTab === 'slides' ? '#ffffff' : 'var(--color-smoke)',
                      padding: '8px 16px',
                      fontFamily: 'var(--font-mono)',
                      fontSize: '12px',
                      cursor: 'pointer',
                      borderRadius: 0,
                      outline: 'none',
                      transition: 'all 0.2s',
                    }}
                    onMouseEnter={e => { if (pptxTab !== 'slides') e.currentTarget.style.borderColor = 'rgba(255,255,255,0.3)' }}
                    onMouseLeave={e => { if (pptxTab !== 'slides') e.currentTarget.style.borderColor = 'var(--color-graphite)' }}
                  >
                    [ СЛАЙДЫ ({slidesList.length}) ]
                  </button>
                  <button
                    onClick={() => setPptxTab('text')}
                    style={{
                      background: pptxTab === 'text' ? 'rgba(255, 255, 255, 0.04)' : 'none',
                      border: `1px solid ${pptxTab === 'text' ? '#8B5CF6' : 'var(--color-graphite)'}`,
                      color: pptxTab === 'text' ? '#ffffff' : 'var(--color-smoke)',
                      padding: '8px 16px',
                      fontFamily: 'var(--font-mono)',
                      fontSize: '12px',
                      cursor: 'pointer',
                      borderRadius: 0,
                      outline: 'none',
                      transition: 'all 0.2s',
                    }}
                    onMouseEnter={e => { if (pptxTab !== 'text') e.currentTarget.style.borderColor = 'rgba(255,255,255,0.3)' }}
                    onMouseLeave={e => { if (pptxTab !== 'text') e.currentTarget.style.borderColor = 'var(--color-graphite)' }}
                  >
                    [ РАСПОЗНАННЫЙ ТЕКСТ ]
                  </button>
                </div>
              )}

              {/* If PPTX or DOCX, display warning banner */}
              {(isPptx || isDocx) && (
                <div style={{
                  padding: '16px 20px',
                  border: '1px solid var(--color-graphite)',
                  background: 'var(--color-carbon)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '12px',
                }}>
                  <FileText size={18} style={{ color: '#3df2b4', flexShrink: 0 }} />
                  <span style={{ fontSize: '13px', color: 'var(--color-smoke)' }}>
                    Вы просматриваете текстовую выжимку из оригинального файла <strong>{lowercaseName.slice(lowercaseName.lastIndexOf('.') + 1).toUpperCase()}</strong>, извлечённую парсером Норникеля для индексации в графе знаний.
                  </span>
                </div>
              )}

              {/* RENDERERS */}
              {isPptx && pptxTab === 'slides' ? (
                /* PPTX Presentation dynamic slide visualizer */
                <div style={{ display: 'flex', flexDirection: 'column', gap: '24px', width: '100%' }}>
                  {/* Dynamic slide card canvas */}
                  <div style={{
                    position: 'relative',
                    width: '100%',
                    aspectRatio: '16/9',
                    background: 'var(--color-carbon)',
                    border: '1px solid var(--color-graphite)',
                    borderRadius: 0,
                    overflow: 'hidden',
                  }}>
                    {renderSlideContent(slidesList[safeCurrentSlide])}
                    
                    {/* Previous slide arrow button */}
                    <button
                      onClick={() => setCurrentSlide(prev => Math.max(0, prev - 1))}
                      disabled={safeCurrentSlide === 0}
                      style={{
                        position: 'absolute',
                        left: '12px',
                        top: '50%',
                        transform: 'translateY(-50%)',
                        background: 'rgba(0, 0, 0, 0.75)',
                        border: '1px solid rgba(255, 255, 255, 0.1)',
                        color: safeCurrentSlide === 0 ? 'rgba(255,255,255,0.15)' : '#ffffff',
                        width: '44px',
                        height: '44px',
                        cursor: safeCurrentSlide === 0 ? 'not-allowed' : 'pointer',
                        fontSize: '18px',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        borderRadius: 0,
                        transition: 'all 0.2s',
                        outline: 'none',
                        zIndex: 20
                      }}
                      onMouseEnter={e => { if (safeCurrentSlide > 0) e.currentTarget.style.borderColor = '#8B5CF6' }}
                      onMouseLeave={e => { if (safeCurrentSlide > 0) e.currentTarget.style.borderColor = 'rgba(255,255,255,0.1)' }}
                    >
                      ←
                    </button>
                    {/* Next slide arrow button */}
                    <button
                      onClick={() => setCurrentSlide(prev => Math.min(slidesList.length - 1, prev + 1))}
                      disabled={safeCurrentSlide === slidesList.length - 1}
                      style={{
                        position: 'absolute',
                        right: '12px',
                        top: '50%',
                        transform: 'translateY(-50%)',
                        background: 'rgba(0, 0, 0, 0.75)',
                        border: '1px solid rgba(255, 255, 255, 0.1)',
                        color: safeCurrentSlide === slidesList.length - 1 ? 'rgba(255,255,255,0.15)' : '#ffffff',
                        width: '44px',
                        height: '44px',
                        cursor: safeCurrentSlide === slidesList.length - 1 ? 'not-allowed' : 'pointer',
                        fontSize: '18px',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        borderRadius: 0,
                        transition: 'all 0.2s',
                        outline: 'none',
                        zIndex: 20
                      }}
                      onMouseEnter={e => { if (safeCurrentSlide < slidesList.length - 1) e.currentTarget.style.borderColor = '#8B5CF6' }}
                      onMouseLeave={e => { if (safeCurrentSlide < slidesList.length - 1) e.currentTarget.style.borderColor = 'rgba(255,255,255,0.1)' }}
                    >
                      →
                    </button>
                  </div>

                  {/* Slide count bar indicator */}
                  <div style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    background: 'var(--color-carbon)',
                    padding: '12px 24px',
                    border: '1px solid var(--color-graphite)',
                    fontFamily: 'var(--font-mono)',
                    fontSize: '12px',
                  }}>
                    <div style={{ color: 'var(--color-smoke)', letterSpacing: '0.05em' }}>
                      СЛАЙД {safeCurrentSlide + 1} ИЗ {slidesList.length}
                    </div>
                    {/* Direct slide indicators (dots) */}
                    <div style={{
                      display: 'flex',
                      gap: '8px',
                      overflowX: 'auto',
                      maxWidth: '50%',
                      padding: '4px 0',
                      scrollbarWidth: 'none',
                      msOverflowStyle: 'none',
                    }}>
                      {slidesList.map((_, idx) => (
                        <button
                          key={idx}
                          onClick={() => setCurrentSlide(idx)}
                          style={{
                            width: '12px',
                            height: '12px',
                            background: safeCurrentSlide === idx ? '#3df2b4' : 'rgba(255,255,255,0.15)',
                            border: 'none',
                            cursor: 'pointer',
                            padding: 0,
                            borderRadius: 0,
                            transition: 'background 0.2s',
                            outline: 'none',
                            flexShrink: 0,
                          }}
                        />
                      ))}
                    </div>
                  </div>

                  {/* Slide thumbnails row selector (dynamically generated text previews) */}
                  <div style={{
                    display: 'flex',
                    overflowX: 'auto',
                    gap: '16px',
                    width: '100%',
                    flexWrap: 'nowrap',
                    paddingBottom: '12px',
                  }}>
                    {slidesList.map((slide, idx) => {
                      const lines = slide.split('\n').map(l => l.trim()).filter(Boolean)
                      const title = lines[0] || `Слайд ${idx + 1}`
                      return (
                        <div
                          key={idx}
                          onClick={() => setCurrentSlide(idx)}
                          style={{
                            border: `1px solid ${safeCurrentSlide === idx ? '#3df2b4' : 'var(--color-graphite)'}`,
                            cursor: 'pointer',
                            aspectRatio: '16/9',
                            background: 'var(--color-carbon)',
                            padding: '12px',
                            boxSizing: 'border-box',
                            display: 'flex',
                            flexDirection: 'column',
                            justifyContent: 'space-between',
                            transition: 'all 0.2s',
                            width: '200px',
                            flexShrink: 0,
                          }}
                          onMouseEnter={e => { if (safeCurrentSlide !== idx) e.currentTarget.style.borderColor = 'rgba(255,255,255,0.3)' }}
                          onMouseLeave={e => { if (safeCurrentSlide !== idx) e.currentTarget.style.borderColor = 'var(--color-graphite)' }}
                        >
                          <div style={{ fontSize: '10px', fontFamily: 'var(--font-mono)', color: '#8B5CF6' }}>
                            СЛАЙД {idx + 1}
                          </div>
                          <div style={{
                            fontSize: '11px',
                            fontWeight: 500,
                            color: 'var(--color-chalk)',
                            whiteSpace: 'nowrap',
                            overflow: 'hidden',
                            textOverflow: 'ellipsis'
                          }}>
                            {title}
                          </div>
                        </div>
                      )
                    })}
                  </div>
                </div>
              ) : isMd ? (
                /* Markdown custom viewer */
                <div style={{
                  border: '1px solid var(--color-graphite)',
                  background: 'var(--color-carbon)',
                  padding: '40px',
                }}>
                  {renderMarkdown(content)}
                </div>
              ) : (
                /* Default lines numbered reader (PDF, DOCX, PPTX text fallback) */
                <div style={{
                  border: '1px solid var(--color-graphite)',
                  background: 'var(--color-carbon)',
                  fontFamily: 'var(--font-aeonik)',
                  fontSize: '14px',
                  lineHeight: 1.6,
                  display: 'flex',
                  flexDirection: 'column',
                }}>
                  {rawLines.map((line, idx) => {
                    const isMatch = searchQuery.trim() && line.toLowerCase().includes(searchQuery.toLowerCase())
                    return (
                      <div
                        key={idx}
                        style={{
                          display: 'flex',
                          borderBottom: '1px solid rgba(255,255,255,0.01)',
                          background: isMatch ? 'rgba(255, 204, 0, 0.08)' : 'transparent',
                        }}
                        onMouseEnter={e => {
                          if (!isMatch) e.currentTarget.style.background = 'rgba(255,255,255,0.01)'
                        }}
                        onMouseLeave={e => {
                          if (!isMatch) e.currentTarget.style.background = 'transparent'
                        }}
                      >
                        {/* Line Number Margin */}
                        <div style={{
                          width: '52px',
                          textAlign: 'right',
                          paddingRight: '12px',
                          color: 'var(--color-iron)',
                          fontFamily: 'var(--font-mono)',
                          fontSize: '10px',
                          borderRight: '1px solid var(--color-graphite)',
                          background: 'rgba(0,0,0,0.15)',
                          paddingTop: '4px',
                          userSelect: 'none',
                        }}>
                          {idx + 1}
                        </div>
                        {/* Line Text */}
                        <div style={{
                          flex: 1,
                          paddingLeft: '16px',
                          paddingRight: '16px',
                          paddingTop: '4px',
                          paddingBottom: '4px',
                          color: isMatch ? 'var(--color-chalk)' : 'var(--color-ash)',
                          wordBreak: 'break-all',
                        }}>
                          {renderLineContent(line) || <span style={{ opacity: 0.15 }}>↵</span>}
                        </div>
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          )}
        </div>
      </main>
    </div>
  )
}

export default function ViewerPage() {
  return (
    <Suspense fallback={<div style={{ padding: '24px', color: 'var(--color-smoke)', fontFamily: 'var(--font-mono)', background: '#0B0B0F', minHeight: '100vh' }}>ЗАГРУЗКА РЕДАКТОРА...</div>}>
      <Suspense>
        <ViewerContent />
      </Suspense>
    </Suspense>
  )
}
