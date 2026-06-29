import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { useMe } from '../hooks/useMe'
import { apiPost } from '../lib/api'
import Card from '../components/ui/Card'

// Hub "Yo": todo lo de cuenta/usuario, antes disperso en el drawer lateral.
export default function Yo() {
  const { data: me } = useMe()
  const qc = useQueryClient()
  const [busy, setBusy] = useState(false)
  const shareAll = !!me?.share_all

  const toggleShareAll = async () => {
    setBusy(true)
    try {
      await apiPost('/api/settings/share_all', { value: shareAll ? 0 : 1 })
      await qc.invalidateQueries() // refresca me + listados afectados por la visibilidad
    } finally {
      setBusy(false)
    }
  }

  return (
    <div style={{ padding: '14px 18px 24px', display: 'grid', gap: 12 }}>
      <div className="cap">Yo</div>

      <Card>
        <div style={{ fontSize: 15, fontWeight: 500 }}>{me?.name ?? '…'}</div>
        <div style={{ fontSize: 13, color: 'var(--color-sage)' }}>{me?.username}</div>
      </Card>

      <Card style={{ display: 'grid', gap: 8 }}>
        <div style={{ fontSize: 14, fontWeight: 600 }}>🔒 Privacidad</div>
        <div style={{ fontSize: 12.5, color: 'var(--color-sage)' }}>
          Todo lo tuyo es privado por default. Podés compartir cosas puntuales (una cuenta, un evento)
          o todo de una con este interruptor. Para ver los datos de tu pareja/hogar usá el selector de arriba.
        </div>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10, marginTop: 2 }}>
          <span style={{ fontSize: 14 }}>Compartir <b>todo</b> con mi pareja/hogar</span>
          <button onClick={toggleShareAll} disabled={busy} style={shareAll ? onBtn : offBtn}>
            {busy ? '…' : shareAll ? 'Activado' : 'Desactivado'}
          </button>
        </div>
      </Card>

      {me?.is_admin && (
        <Link to="/admin" style={rowLink}><i className="ti ti-shield-lock" style={{ marginRight: 8 }} aria-hidden />Panel de administración</Link>
      )}
      <a href="/api/export.csv" style={rowLink}><i className="ti ti-download" style={{ marginRight: 8 }} aria-hidden />Exportar CSV</a>
      <button onClick={logout} style={rowBtn}><i className="ti ti-logout" style={{ marginRight: 8 }} aria-hidden />Cerrar sesión</button>
      <a href="/legacy/" style={{ ...rowLink, color: 'var(--color-sage)', fontSize: 13 }}>Dashboard viejo →</a>
    </div>
  )
}

async function logout() {
  try { await fetch('/logout', { credentials: 'include' }) } catch { /* ignore */ }
  location.assign('/app/login')
}

const rowLink: React.CSSProperties = { color: 'var(--color-obsidian-ink)', textDecoration: 'none', fontSize: 15, padding: '8px 0', display: 'flex', alignItems: 'center' }
const rowBtn: React.CSSProperties = { ...rowLink, background: 'none', border: 'none', textAlign: 'left', cursor: 'pointer', font: 'inherit' }
const onBtn: React.CSSProperties = { background: 'var(--color-voltage)', color: 'var(--voltage-on-dark)', border: 'none', borderRadius: 9999, padding: '6px 14px', fontSize: 13, fontWeight: 500, cursor: 'pointer', font: 'inherit', flexShrink: 0 }
const offBtn: React.CSSProperties = { ...onBtn, background: 'var(--color-mist)', color: 'var(--color-sage)' }
