import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { useMe } from '../hooks/useMe'
import { apiPost } from '../lib/api'
import Card from '../components/ui/Card'
import SettingHeader from '../components/ui/SettingHeader'
import ThemeToggle from '../components/ThemeToggle'
import NotifToggle from '../components/NotifToggle'
import CalendarSubscribe from '../components/CalendarSubscribe'
import HouseholdCard from '../components/HouseholdCard'

// Hub "Yo": perfil + ajustes (privacidad, tema, notificaciones, calendario, cuenta).
export default function Yo() {
  const { data: me } = useMe()
  const qc = useQueryClient()
  const [busy, setBusy] = useState(false)
  const shareAll = !!me?.share_all
  const initial = (me?.name?.[0] ?? '·').toUpperCase()

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
    <div style={{ padding: '14px 18px 28px', display: 'grid', gap: 14 }}>
      <div className="cap">Yo</div>

      {/* Perfil */}
      <Card>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={avatar}>{initial}</span>
          <div style={{ minWidth: 0 }}>
            <div style={{ fontSize: 16, fontWeight: 500 }}>{me?.name ?? '…'}</div>
            {me?.username && <div style={{ fontSize: 13, color: 'var(--color-sage)' }}>@{me.username}</div>}
          </div>
        </div>
      </Card>

      {/* Pareja / familia */}
      <HouseholdCard />

      {/* Privacidad */}
      <Card style={{ display: 'grid', gap: 12 }}>
        <SettingHeader icon="ti-lock" title="Privacidad" />
        <p style={hint}>
          Todo lo que cargás es <b>privado</b>: solo lo ves vos. Podés compartir cosas sueltas
          (una cuenta, una nota, una lista) desde cada una, o todo de una con el interruptor de abajo.
        </p>
        <div style={rowBetween}>
          <div style={{ minWidth: 0, paddingRight: 10 }}>
            <div style={{ fontSize: 14 }}>Compartir todo con mi hogar</div>
            <div style={subHint}>
              {shareAll
                ? 'Las personas de tu plan ven todo lo tuyo (cuentas, gastos, tareas, listas, notas y agenda).'
                : 'Solo ves lo tuyo. Nadie de tu plan ve tus cosas salvo las que compartas a mano.'}
            </div>
          </div>
          <button onClick={toggleShareAll} disabled={busy} style={shareAll ? onBtn : offBtn}>
            {busy ? '…' : shareAll ? 'Activado' : 'Desactivado'}
          </button>
        </div>
      </Card>

      <ThemeToggle />
      <NotifToggle />
      <CalendarSubscribe />

      {/* Cuenta */}
      <Card style={{ padding: '2px 14px' }}>
        {me?.is_admin && <Row to="/admin" icon="ti-shield-lock" label="Panel de administración" />}
        <Row href="/api/export.csv" icon="ti-download" label="Exportar CSV" />
        <Row onClick={logout} icon="ti-logout" label="Cerrar sesión" />
        <Row href="/legacy/" icon="ti-external-link" label="Dashboard viejo" muted last />
      </Card>
    </div>
  )
}

// Fila de acción reutilizable (link interno, link externo o botón).
function Row({ to, href, onClick, icon, label, muted, last }: {
  to?: string; href?: string; onClick?: () => void; icon: string; label: string; muted?: boolean; last?: boolean
}) {
  const inner = (
    <>
      <i className={`ti ${icon}`} style={{ fontSize: 18, color: muted ? 'var(--color-sage)' : 'var(--color-obsidian-ink)' }} aria-hidden />
      <span style={{ flex: 1 }}>{label}</span>
      {(to || href) && !muted && <i className="ti ti-chevron-right" style={{ fontSize: 16, color: 'var(--color-sage)' }} aria-hidden />}
    </>
  )
  const style: React.CSSProperties = {
    display: 'flex', alignItems: 'center', gap: 10, width: '100%',
    padding: '13px 0', fontSize: 15, font: 'inherit', textAlign: 'left',
    color: muted ? 'var(--color-sage)' : 'var(--color-obsidian-ink)',
    background: 'none', border: 'none', cursor: 'pointer', textDecoration: 'none',
    borderBottom: last ? 'none' : '1px solid var(--color-mist)',
  }
  if (to) return <Link to={to} style={style}>{inner}</Link>
  if (href) return <a href={href} style={style}>{inner}</a>
  return <button onClick={onClick} style={style}>{inner}</button>
}

async function logout() {
  try { await fetch('/logout', { credentials: 'include' }) } catch { /* ignore */ }
  location.assign('/app/login')
}

const avatar: React.CSSProperties = {
  width: 46, height: 46, borderRadius: '50%', flexShrink: 0,
  background: 'var(--color-pollen)', color: 'var(--voltage-on-dark)',
  display: 'inline-flex', alignItems: 'center', justifyContent: 'center', fontSize: 18, fontWeight: 500,
}
const hint: React.CSSProperties = { margin: 0, fontSize: 12.5, color: 'var(--color-sage)', lineHeight: 1.5 }
const subHint: React.CSSProperties = { fontSize: 11.5, color: 'var(--color-sage)', lineHeight: 1.45, marginTop: 2 }
const rowBetween: React.CSSProperties = { display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10 }
const onBtn: React.CSSProperties = { background: 'var(--color-voltage)', color: 'var(--voltage-on-dark)', border: 'none', borderRadius: 9999, padding: '7px 15px', fontSize: 13, fontWeight: 500, cursor: 'pointer', font: 'inherit', flexShrink: 0 }
const offBtn: React.CSSProperties = { ...onBtn, background: 'var(--color-mist)', color: 'var(--color-sage)' }
