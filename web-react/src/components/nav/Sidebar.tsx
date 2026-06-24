import { NavLink } from 'react-router-dom'
import { SIDEBAR_GROUPS } from './navItems'

export default function Sidebar({ onAdd }: { onAdd: () => void }) {
  return (
    <aside style={{ width: 220, borderRight: '1px solid var(--color-mist)', padding: 24, display: 'grid', gap: 6, alignContent: 'start' }}>
      <button onClick={onAdd} style={{
        background: 'var(--color-voltage)', color: 'var(--voltage-on-dark)', border: 'none', borderRadius: 10,
        padding: '12px 16px', fontWeight: 500, marginBottom: 16, cursor: 'pointer',
      }}>+ Agregar</button>
      {SIDEBAR_GROUPS.map((group, gi) => (
        <div key={gi} style={{ marginBottom: 8 }}>
          {group.title && (
            <div className="cap" style={{ padding: '4px 0 6px', fontSize: 10, letterSpacing: '0.08em', color: 'var(--color-sage)' }}>
              {group.title}
            </div>
          )}
          {group.items.map((i) => (
            <NavLink key={i.to} to={i.to} end={i.to === '/'} style={({ isActive }) => ({
              color: isActive ? 'var(--color-obsidian-ink)' : 'var(--color-sage)',
              textDecoration: 'none', fontSize: 15, padding: '8px 0', fontWeight: isActive ? 500 : 400,
              display: 'block',
            })}>
              <i className={`ti ${i.icon}`} style={{ marginRight: 8 }} aria-hidden />{i.label}
            </NavLink>
          ))}
          {gi < SIDEBAR_GROUPS.length - 1 && (
            <div style={{ height: 1, background: 'var(--color-mist)', margin: '8px 0' }} />
          )}
        </div>
      ))}
    </aside>
  )
}
