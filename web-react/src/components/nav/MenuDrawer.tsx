import { Link } from 'react-router-dom'

export default function MenuDrawer({ open, onClose }: { open: boolean; onClose: () => void }) {
  if (!open) return null
  const links = [
    { to: '/categorias', label: 'Categorías y presupuestos' },
    { to: '/perfil', label: 'Perfil y cuenta' },
  ]
  return (
    <div onClick={onClose} style={{ minHeight: 400, position: 'relative', background: 'rgba(18,22,19,0.45)' }}>
      <div onClick={(e) => e.stopPropagation()} style={{
        background: 'var(--color-linen)', padding: 24, display: 'grid', gap: 16,
      }}>
        {links.map((l) => (
          <Link key={l.to} to={l.to} onClick={onClose} style={{ color: 'var(--color-obsidian-ink)', textDecoration: 'none', fontSize: 16 }}>{l.label}</Link>
        ))}
        <a href="/legacy/" style={{ color: 'var(--color-sage)', fontSize: 14 }}>Otras secciones (hábitos, notas, tareas) →</a>
      </div>
    </div>
  )
}
