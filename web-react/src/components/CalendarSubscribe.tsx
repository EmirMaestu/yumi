import { useState } from 'react'
import { apiGet, apiPost } from '../lib/api'
import Card from './ui/Card'

// webcal:// hace que el iPhone/Apple Calendar ofrezca "Suscribirse" de un toque.
function toWebcal(u: string): string {
  return u.replace(/^https?:\/\//i, 'webcal://')
}

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
    return <button onClick={load} style={linkBtn}>📅 Suscribir mi calendario</button>
  }

  return (
    <Card style={{ display: 'grid', gap: 10 }}>
      <div style={{ fontSize: 14, fontWeight: 600 }}>📅 Tu calendario en Google / Apple</div>
      <div style={{ fontSize: 12.5, color: 'var(--color-sage)' }}>
        Vas a ver tus <b>eventos y recordatorios</b> de Yumi dentro de tu calendario. Es de solo lectura
        y se actualiza solo cada varias horas (no al instante).
      </div>
      {loading && <div style={{ fontSize: 13 }}>Cargando…</div>}
      {url && (
        <>
          {/* iPhone / Apple — un toque */}
          <a href={toWebcal(url)} style={primaryLink}>📱 Suscribir en iPhone / Apple (un toque)</a>
          <div style={{ fontSize: 11.5, color: 'var(--color-sage)', lineHeight: 1.5 }}>
            Tocá ese botón <b>desde el iPhone</b> y confirmá "Suscribirse". Si no se abre solo: Ajustes →
            Calendario → Cuentas → Agregar cuenta → Otra → <b>Agregar calendario suscrito</b> → pegá el link de abajo.
          </div>

          {/* Google — solo desde computadora */}
          <div style={{ fontSize: 11.5, color: 'var(--color-sage)', lineHeight: 1.55, borderTop: '1px solid var(--color-mist)', paddingTop: 8 }}>
            <b>Google Calendar — solo desde una computadora</b> (la app del celular no deja agregar por URL):<br />
            1. Entrá a <b>calendar.google.com</b>.<br />
            2. A la izquierda, al lado de <b>"Otros calendarios"</b>, tocá el <b>+</b> → <b>"Desde URL"</b>.<br />
            3. Pegá el link de abajo y tocá <b>"Agregar calendario"</b>.<br />
            (La primera vez puede tardar unas horas en aparecer.)
          </div>

          <div style={{ fontSize: 12, wordBreak: 'break-all', background: 'var(--color-mist)', padding: 8, borderRadius: 8 }}>{url}</div>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <button onClick={copy} style={primaryBtn}>{copied ? '¡Copiado!' : 'Copiar link'}</button>
            <button onClick={regenerate} style={ghostBtn}>Regenerar link</button>
          </div>
        </>
      )}
    </Card>
  )
}

const linkBtn: React.CSSProperties = {
  background: 'transparent', border: '1px solid var(--color-mist)', borderRadius: 10,
  padding: '8px 12px', fontSize: 13, cursor: 'pointer', color: 'var(--color-obsidian-ink)', font: 'inherit', textAlign: 'left',
}
const primaryBtn: React.CSSProperties = {
  background: 'var(--color-voltage)', color: 'var(--voltage-on-dark)', border: 'none',
  borderRadius: 10, padding: '9px 14px', fontSize: 13, fontWeight: 500, cursor: 'pointer', font: 'inherit',
}
const primaryLink: React.CSSProperties = {
  ...primaryBtn, display: 'inline-block', textDecoration: 'none', textAlign: 'center',
}
const ghostBtn: React.CSSProperties = {
  background: 'var(--color-linen)', border: '1px solid var(--color-mist)', borderRadius: 10,
  padding: '9px 14px', fontSize: 13, cursor: 'pointer', color: 'var(--color-obsidian-ink)', font: 'inherit',
}
