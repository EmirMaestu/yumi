import { Link } from 'react-router-dom'

export default function MenuDrawer({ open, onClose }: { open: boolean; onClose: () => void }) {
  if (!open) return null
  const links = [
    { to: '/recurrentes', label: 'Recurrentes y cuotas' },
    { to: '/categorias', label: 'Categorías y presupuestos' },
    { to: '/perfil', label: 'Perfil y cuenta' },
  ]
  return (
    <div
      onClick={onClose}
      style={{ position: 'fixed', inset: 0, zIndex: 60, background: 'rgba(18,22,19,0.45)', display: 'flex', justifyContent: 'flex-end' }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{ width: '78%', maxWidth: 320, height: '100%', background: 'var(--color-linen)', padding: 24, display: 'grid', gap: 16, alignContent: 'start' }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span className="cap">Menú</span>
          <button onClick={onClose} aria-label="Cerrar" style={{ background: 'none', border: 'none', cursor: 'pointer' }}>
            <i className="ti ti-x" style={{ fontSize: 20 }} aria-hidden />
          </button>
        </div>
        {links.map((l) => (
          <Link key={l.to} to={l.to} onClick={onClose} style={{ color: 'var(--color-obsidian-ink)', textDecoration: 'none', fontSize: 16 }}>{l.label}</Link>
        ))}
        <a href="/legacy/" style={{ color: 'var(--color-sage)', fontSize: 14, textDecoration: 'none' }}>Otras secciones (hábitos, notas, tareas) →</a>
      </div>
    </div>
  )
}
