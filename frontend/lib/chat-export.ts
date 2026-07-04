import type { ChatMessage } from '@/lib/api'

type ExportableChatSession = {
  title?: string
} | null

const PDF_PAGE_WIDTH = 1240
const PDF_PAGE_HEIGHT = 1754
const PDF_MARGIN_X = 88
const PDF_MARGIN_Y = 92
const PDF_LINE_HEIGHT = 30
const PDF_BODY_FONT = "24px 'Red Hat Text', sans-serif"
const PDF_TITLE_FONT = "bold 40px 'Red Hat Display', sans-serif"
const PDF_META_FONT = "20px 'Red Hat Mono', monospace"

type PdfPageImage = {
  bytes: Uint8Array
  width: number
  height: number
}

export function exportChatAsMarkdown(session: ExportableChatSession, messages: ChatMessage[]) {
  const markdown = buildChatMarkdown(session, messages)
  const filename = `${makeSafeFilename(session?.title || 'chat-history')}.md`
  downloadBlob(filename, new Blob([markdown], { type: 'text/markdown;charset=utf-8' }))
}

export async function exportChatAsPdf(session: ExportableChatSession, messages: ChatMessage[]) {
  const plainText = buildChatPlainText(session, messages)
  const pages = await renderPdfPages(session?.title || 'История чата', plainText)
  const pdfBlob = buildPdfFromImages(pages)
  const filename = `${makeSafeFilename(session?.title || 'chat-history')}.pdf`
  downloadBlob(filename, pdfBlob)
}

function buildChatMarkdown(session: ExportableChatSession, messages: ChatMessage[]) {
  const lines: string[] = [
    `# ${session?.title || 'История чата'}`,
    '',
    `Экспортировано: ${formatTimestamp(Date.now() / 1000)}`,
    '',
  ]

  for (const message of messages) {
    lines.push(`## ${message.role === 'user' ? 'Вопрос' : message.error ? 'Ошибка' : 'Ответ GraphRAG'}`)
    lines.push('')
    lines.push(message.content || '')
    lines.push('')

    if (message.cached) {
      lines.push('- Источник ответа: кэш')
    }

    if (message.sources?.length) {
      lines.push(`- Источники: ${message.sources.join(', ')}`)
    }

    if (message.facts?.length) {
      lines.push('- Факты:')
      for (const fact of message.facts) {
        lines.push(
          `  - ${fact.subject} · ${fact.predicate} = ${fact.value} ` +
          `(confidence ${Math.round((fact.confidence || 0) * 100)}%` +
          `${fact.geography && fact.geography !== 'unknown' ? `, ${fact.geography}` : ''})`,
        )
      }
    }

    lines.push('')
  }

  return lines.join('\n').trimEnd() + '\n'
}

function buildChatPlainText(session: ExportableChatSession, messages: ChatMessage[]) {
  const lines: string[] = [
    session?.title || 'История чата',
    '',
    `Экспортировано: ${formatTimestamp(Date.now() / 1000)}`,
    '',
  ]

  for (const message of messages) {
    lines.push(message.role === 'user' ? 'Вопрос' : message.error ? 'Ошибка' : 'Ответ GraphRAG')
    lines.push(message.content || '')

    if (message.cached) {
      lines.push('Источник ответа: кэш')
    }

    if (message.sources?.length) {
      lines.push(`Источники: ${message.sources.join(', ')}`)
    }

    if (message.facts?.length) {
      lines.push('Факты:')
      for (const fact of message.facts) {
        lines.push(
          `- ${fact.subject} · ${fact.predicate} = ${fact.value} ` +
          `(confidence ${Math.round((fact.confidence || 0) * 100)}%` +
          `${fact.geography && fact.geography !== 'unknown' ? `, ${fact.geography}` : ''})`,
        )
      }
    }

    lines.push('')
  }

  return lines.join('\n').trim()
}

async function renderPdfPages(title: string, text: string) {
  const pages: PdfPageImage[] = []
  const paragraphs = text.split('\n')
  let canvas = document.createElement('canvas')
  let ctx = preparePageCanvas(canvas)
  let cursorY = PDF_MARGIN_Y
  let pageNumber = 1

  const startPage = () => {
    canvas = document.createElement('canvas')
    ctx = preparePageCanvas(canvas)
    cursorY = PDF_MARGIN_Y
    drawPageHeader(ctx, title, pageNumber)
    cursorY += 110
    pageNumber += 1
  }

  const flushPage = () => {
    pages.push({
      bytes: dataUrlToBytes(canvas.toDataURL('image/jpeg', 0.92)),
      width: PDF_PAGE_WIDTH,
      height: PDF_PAGE_HEIGHT,
    })
  }

  startPage()

  for (const paragraph of paragraphs) {
    const wrapped = wrapText(ctx, paragraph, PDF_PAGE_WIDTH - PDF_MARGIN_X * 2)
    const lines = wrapped.length ? wrapped : ['']

    for (const line of lines) {
      if (cursorY + PDF_LINE_HEIGHT > PDF_PAGE_HEIGHT - PDF_MARGIN_Y) {
        flushPage()
        startPage()
      }

      ctx.font = PDF_BODY_FONT
      ctx.fillStyle = '#0f172a'
      ctx.fillText(line, PDF_MARGIN_X, cursorY)
      cursorY += PDF_LINE_HEIGHT
    }
  }

  flushPage()
  return pages
}

function preparePageCanvas(canvas: HTMLCanvasElement) {
  canvas.width = PDF_PAGE_WIDTH
  canvas.height = PDF_PAGE_HEIGHT
  const ctx = canvas.getContext('2d')

  if (!ctx) {
    throw new Error('Canvas is not available for PDF export')
  }

  ctx.fillStyle = '#ffffff'
  ctx.fillRect(0, 0, PDF_PAGE_WIDTH, PDF_PAGE_HEIGHT)
  ctx.textBaseline = 'top'
  return ctx
}

function drawPageHeader(ctx: CanvasRenderingContext2D, title: string, pageNumber: number) {
  ctx.fillStyle = '#020617'
  ctx.font = PDF_TITLE_FONT

  for (const [index, line] of wrapText(ctx, title, PDF_PAGE_WIDTH - PDF_MARGIN_X * 2).slice(0, 2).entries()) {
    ctx.fillText(line, PDF_MARGIN_X, PDF_MARGIN_Y + index * 46)
  }

  ctx.font = PDF_META_FONT
  ctx.fillStyle = '#475569'
  ctx.fillText(`GraphRAG export · page ${pageNumber}`, PDF_MARGIN_X, PDF_MARGIN_Y + 82)
  ctx.strokeStyle = '#cbd5e1'
  ctx.lineWidth = 2
  ctx.beginPath()
  ctx.moveTo(PDF_MARGIN_X, PDF_MARGIN_Y + 118)
  ctx.lineTo(PDF_PAGE_WIDTH - PDF_MARGIN_X, PDF_MARGIN_Y + 118)
  ctx.stroke()
}

function wrapText(ctx: CanvasRenderingContext2D, text: string, maxWidth: number) {
  if (!text) return []

  const out: string[] = []
  let line = ''

  for (const word of text.split(/\s+/)) {
    if (!word) continue

    const candidate = line ? `${line} ${word}` : word
    if (ctx.measureText(candidate).width <= maxWidth) {
      line = candidate
      continue
    }

    if (line) out.push(line)

    if (ctx.measureText(word).width <= maxWidth) {
      line = word
      continue
    }

    let segment = ''
    for (const char of word) {
      const test = segment + char
      if (ctx.measureText(test).width > maxWidth && segment) {
        out.push(segment)
        segment = char
      } else {
        segment = test
      }
    }
    line = segment
  }

  if (line) out.push(line)
  return out
}

function buildPdfFromImages(pages: PdfPageImage[]) {
  const encoder = new TextEncoder()
  const chunks: Uint8Array[] = []
  const offsets: number[] = [0]
  let totalLength = 0
  let objectId = 1

  const appendBytes = (bytes: Uint8Array) => {
    chunks.push(bytes)
    totalLength += bytes.length
  }

  const appendText = (text: string) => {
    appendBytes(encoder.encode(text))
  }

  const registerOffset = (id: number) => {
    offsets[id] = totalLength
  }

  appendText('%PDF-1.4\n')

  const pageIds: number[] = []
  const imageIds: number[] = []
  const contentIds: number[] = []
  const pagesRootId = 2

  registerOffset(objectId)
  appendText('1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n')
  objectId += 1

  const pageObjectStart = 3
  for (let index = 0; index < pages.length; index += 1) {
    pageIds.push(pageObjectStart + index * 3)
    imageIds.push(pageObjectStart + index * 3 + 1)
    contentIds.push(pageObjectStart + index * 3 + 2)
  }

  registerOffset(pagesRootId)
  appendText(
    `2 0 obj\n<< /Type /Pages /Count ${pages.length} /Kids [` +
    `${pageIds.map(id => `${id} 0 R`).join(' ')}] >>\nendobj\n`,
  )

  for (let index = 0; index < pages.length; index += 1) {
    const pageId = pageIds[index]
    const imageId = imageIds[index]
    const contentId = contentIds[index]
    const image = pages[index]
    const imageName = `Im${index + 1}`
    const contentStream = encoder.encode(`q\n595 0 0 842 0 0 cm\n/${imageName} Do\nQ\n`)

    registerOffset(pageId)
    appendText(
      `${pageId} 0 obj\n` +
      `<< /Type /Page /Parent ${pagesRootId} 0 R /MediaBox [0 0 595 842] ` +
      `/Resources << /XObject << /${imageName} ${imageId} 0 R >> >> ` +
      `/Contents ${contentId} 0 R >>\nendobj\n`,
    )

    registerOffset(imageId)
    appendText(
      `${imageId} 0 obj\n` +
      `<< /Type /XObject /Subtype /Image /Width ${image.width} /Height ${image.height} ` +
      `/ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode /Length ${image.bytes.length} >>\nstream\n`,
    )
    appendBytes(image.bytes)
    appendText('\nendstream\nendobj\n')

    registerOffset(contentId)
    appendText(
      `${contentId} 0 obj\n` +
      `<< /Length ${contentStream.length} >>\nstream\n`,
    )
    appendBytes(contentStream)
    appendText('endstream\nendobj\n')
  }

  const xrefOffset = totalLength
  appendText(`xref\n0 ${offsets.length}\n`)
  appendText('0000000000 65535 f \n')
  for (let id = 1; id < offsets.length; id += 1) {
    appendText(`${String(offsets[id] || 0).padStart(10, '0')} 00000 n \n`)
  }
  appendText(
    `trailer\n<< /Size ${offsets.length} /Root 1 0 R >>\n` +
    `startxref\n${xrefOffset}\n%%EOF`,
  )

  return new Blob(chunks, { type: 'application/pdf' })
}

function dataUrlToBytes(dataUrl: string) {
  const [, base64 = ''] = dataUrl.split(',')
  const binary = atob(base64)
  const bytes = new Uint8Array(binary.length)

  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index)
  }

  return bytes
}

function downloadBlob(filename: string, blob: Blob) {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  window.setTimeout(() => URL.revokeObjectURL(url), 1000)
}

function makeSafeFilename(value: string) {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9а-яё_-]+/giu, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 64) || 'chat-export'
}

function formatTimestamp(unixSeconds: number) {
  return new Intl.DateTimeFormat('ru-RU', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(unixSeconds * 1000))
}
