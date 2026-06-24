import { useMe } from '../hooks/useMe'
import Card from '../components/ui/Card'

export default function Perfil() {
  const { data: me } = useMe()
  return (
    <div style={{ padding: '14px 18px 24px', display: 'grid', gap: 12 }}>
      <div className="cap">Perfil</div>
      <Card>
        <div style={{ fontSize: 15, fontWeight: 500 }}>{me?.name ?? '…'}</div>
        <div style={{ fontSize: 13, color: 'var(--color-sage)' }}>{me?.username}</div>
      </Card>
      <a href="/api/export.csv" style={linkStyle}><i className="ti ti-download" style={{ marginRight: 8 }} aria-hidden />Exportar CSV</a>
      <button onClick={logout} style={logoutBtnStyle}><i className="ti ti-logout" style={{ marginRight: 8 }} aria-hidden />Cerrar sesión</button>
    </div>
  )
}

async function logout() {
  // clear the server session, then land on the app's own login (not the legacy /login)
  try { await fetch('/logout', { credentials: 'include' }) } catch { /* ignore */ }
  location.assign('/app/login')
}

const linkStyle: React.CSSProperties = { color: 'var(--color-obsidian-ink)', textDecoration: 'none', fontSize: 15, padding: '8px 0' }
const logoutBtnStyle: React.CSSProperties = { ...linkStyle, background: 'none', border: 'none', textAlign: 'left', cursor: 'pointer', font: 'inherit', display: 'flex', alignItems: 'center' }
