import { useState } from 'react'
import { apiGet, apiPost } from '../lib/api'
import Card from './ui/Card'

export default function CalendarSubscribe() {
  const [open, setOpen] = useState(false)
  const [url, setUrl] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [copied, setCopied] = useState(false)

  const load = async () => {
    setOpen(true)
    if (url) return
    setLoading(true)
    try {
      const r = await apiGet<{ url: string }>('/api/cal/url')
      setUrl(r.url)
    } finally {
      setLoading(false)
    }
  }

  const regenerate = async () => {
    if (!window.confirm('Vas a generar un link nuevo. El calendario que ya tengas suscripto va a dejar de actualizarse. ¿Seguir?')) return
    setLoading(true)
    try {
      const r = await apiPost<{ url: string }>('/api/cal/regenerate')
      setUrl(r.url)
      setCopied(false)
    } finally {
      setLoading(false)
    }
  }

  const copy = () => {
    if (!url) return
    navigator.clipboard?.writeText(url).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    }).catch(() => {})
  }

  if (!open) {
    return (
      <button onClick={load} style={linkBtn}>📅 Suscribir a mi calendario</button>
    )
  }

  return (
    <Card style={{ display: 'grid', gap: 10, background: 'var(--color-mist)', border: 'none' }}>
      <div style={{ fontSize: 14, fontWeight: 600 }}>📅 Suscribir a mi calendario</div>
      <div style={{ fontSize: 12.5, color: 'var(--color-sage)' }}>
        Pegá este link en Google/Apple/Outlook Calendar y vas a ver tus eventos y recordatorios de Yumi ahí.
        (Se actualiza cada varias horas, no al instante.)
      </div>
      {loading && <div style={{ fontSize: 13 }}>Cargando…</div>}
      {url && (
        <>
          <div style={{ fontSize: 12, wordBreak: 'break-all', background: 'var(--color-linen)', padding: 8, borderRadius: 8 }}>{url}</div>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <button onClick={copy} style={primaryBtn}>{copied ? '¡Copiado!' : 'Copiar link'}</button>
            <button onClick={regenerate} style={ghostBtn}>Regenerar</button>
          </div>
          <div style={{ fontSize: 11.5, color: 'var(--color-sage)', lineHeight: 1.5 }}>
            <b>Google:</b> Otros calendarios → Desde URL → pegá el link.<br />
            <b>iPhone:</b> Ajustes → Calendario → Cuentas → Agregar cuenta → Otro → Agregar calendario suscrito.
          </div>
        </>
      )}
    </Card>
  )
}

const linkBtn: React.CSSProperties = {
  background: 'transparent', border: '1px solid var(--color-mist)', borderRadius: 10,
  padding: '8px 12px', fontSize: 13, cursor: 'pointer', color: 'var(--color-obsidian-ink)', font: 'inherit',
}
const primaryBtn: React.CSSProperties = {
  background: 'var(--color-voltage)', color: 'var(--voltage-on-dark)', border: 'none',
  borderRadius: 10, padding: '9px 14px', fontSize: 13, fontWeight: 500, cursor: 'pointer', font: 'inherit',
}
const ghostBtn: React.CSSProperties = {
  background: 'var(--color-linen)', border: '1px solid var(--color-mist)', borderRadius: 10,
  padding: '9px 14px', fontSize: 13, cursor: 'pointer', color: 'var(--color-obsidian-ink)', font: 'inherit',
}
