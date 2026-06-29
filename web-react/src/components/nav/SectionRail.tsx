import { Link } from 'react-router-dom'
import type { NavItem } from './navItems'

// Riel horizontal de "chips" que llevan a las sub-secciones de un hub.
// Hace visibles y descubribles las secciones que antes vivían en el drawer.
export default function SectionRail({ items }: { items: NavItem[] }) {
  return (
    <div style={{ display: 'flex', gap: 8, overflowX: 'auto', padding: '2px 0', scrollbarWidth: 'none' }}>
      {items.map((i) => (
        <Link key={i.to} to={i.to} style={chip}>
          <i className={`ti ${i.icon}`} aria-hidden style={{ fontSize: 15, color: 'var(--color-sage)' }} />
          <span>{i.label}</span>
        </Link>
      ))}
    </div>
  )
}

const chip: React.CSSProperties = {
  display: 'inline-flex', alignItems: 'center', gap: 6, flex: '0 0 auto',
  textDecoration: 'none', color: 'var(--color-obsidian-ink)',
  border: '1px solid var(--color-mist)', borderRadius: 9999,
  padding: '7px 13px', fontSize: 13, background: 'var(--color-linen)', whiteSpace: 'nowrap',
}
