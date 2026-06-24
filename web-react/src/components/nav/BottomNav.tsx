import { NavLink } from 'react-router-dom'
import { BOTTOM_NAV } from './navItems'

export default function BottomNav({ onAdd }: { onAdd: () => void }) {
  return (
    <nav style={{ position: 'fixed', left: 0, right: 0, bottom: 0, zIndex: 40, background: 'var(--color-linen)', borderTop: '1px solid var(--color-mist)' }}>
      <div style={{ maxWidth: 480, margin: '0 auto', display: 'flex', alignItems: 'center', justifyContent: 'space-around', padding: '12px 14px 18px' }}>
        {BOTTOM_NAV.slice(0, 2).map((i) => <Item key={i.to} {...i} />)}
        <button onClick={onAdd} aria-label="Agregar"
          style={{
            width: 52, height: 52, borderRadius: '50%', background: 'var(--color-voltage)',
            border: 'none', boxShadow: 'var(--shadow-cta)', marginTop: -26, cursor: 'pointer',
          }}>
          <i className="ti ti-plus" style={{ fontSize: 26, color: 'var(--voltage-on-dark)' }} aria-hidden />
        </button>
        {BOTTOM_NAV.slice(2).map((i) => <Item key={i.to} {...i} />)}
      </div>
    </nav>
  )
}

function Item({ to, label, icon }: { to: string; label: string; icon: string }) {
  return (
    <NavLink to={to} end={to === '/'} style={{ textDecoration: 'none' }}>
      {({ isActive }) => (
        <span style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 3,
          color: isActive ? 'var(--color-obsidian-ink)' : 'var(--color-sage)' }}>
          <i className={`ti ${icon}`} style={{ fontSize: 21 }} aria-hidden />
          <span style={{ fontSize: 10, fontWeight: isActive ? 500 : 400 }}>{label}</span>
          {isActive && <span style={{ width: 5, height: 5, borderRadius: '50%', background: 'var(--color-voltage)' }} />}
        </span>
      )}
    </NavLink>
  )
}
