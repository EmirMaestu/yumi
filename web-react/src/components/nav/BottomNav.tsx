import { NavLink } from 'react-router-dom'
import { BOTTOM_NAV } from './navItems'

// Barra inferior estilo "liquid glass" (tipo iOS 26 / Apple Music):
// pill flotante, translúcida con blur del fondo, borde hairline y sombra suave.
// El <nav> ocupa todo el ancho pero con pointer-events:none, y solo la pill captura
// toques → los costados dejan pasar el tap al contenido de atrás.
export default function BottomNav({ onAdd, onMore }: { onAdd: () => void; onMore: () => void }) {
  return (
    <nav
      aria-label="Navegación principal"
      style={{
        position: 'fixed', left: 0, right: 0,
        bottom: 'calc(env(safe-area-inset-bottom, 0px) + 12px)',
        zIndex: 40, display: 'flex', justifyContent: 'center',
        pointerEvents: 'none',
      }}
    >
      <div
        style={{
          pointerEvents: 'auto',
          display: 'flex', alignItems: 'center', justifyContent: 'space-around', gap: 2,
          width: 'min(440px, calc(100vw - 24px))',
          padding: '8px 12px',
          borderRadius: 30,
          background: 'color-mix(in srgb, var(--color-linen) 68%, transparent)',
          backdropFilter: 'blur(24px) saturate(180%)',
          WebkitBackdropFilter: 'blur(24px) saturate(180%)',
          border: '1px solid rgba(255,255,255,0.45)',
          boxShadow: '0 10px 34px rgba(18,22,19,0.18), inset 0 1px 0 rgba(255,255,255,0.55)',
        }}
      >
        {BOTTOM_NAV.slice(0, 2).map((i) => <Item key={i.to} {...i} />)}
        <button onClick={onAdd} aria-label="Agregar"
          style={{
            width: 50, height: 50, borderRadius: '50%', background: 'var(--color-voltage)',
            border: 'none', boxShadow: 'var(--shadow-cta)', marginTop: -22, flex: '0 0 auto',
            cursor: 'pointer', display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
          }}>
          <i className="ti ti-plus" style={{ fontSize: 26, color: 'var(--voltage-on-dark)' }} aria-hidden />
        </button>
        {BOTTOM_NAV.slice(2).map((i) => <Item key={i.to} {...i} />)}
        <button onClick={onMore} aria-label="Más"
          style={{
            flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2,
            background: 'none', border: 'none', cursor: 'pointer', font: 'inherit',
            padding: '6px 4px', color: 'var(--color-sage)',
          }}>
          <i className="ti ti-dots" style={{ fontSize: 21 }} aria-hidden />
          <span style={{ fontSize: 10, fontWeight: 400 }}>Más</span>
        </button>
      </div>
    </nav>
  )
}

function Item({ to, label, icon }: { to: string; label: string; icon: string }) {
  return (
    <NavLink to={to} end={to === '/'} style={{ textDecoration: 'none', flex: 1 }}>
      {({ isActive }) => (
        <span style={{
          display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2,
          padding: '6px 4px', borderRadius: 16,
          background: isActive ? 'color-mix(in srgb, var(--color-voltage) 18%, transparent)' : 'transparent',
          color: isActive ? 'var(--color-obsidian-ink)' : 'var(--color-sage)',
          transition: 'background 160ms ease, color 160ms ease',
        }}>
          <i className={`ti ${icon}`} style={{ fontSize: 21 }} aria-hidden />
          <span style={{ fontSize: 10, fontWeight: isActive ? 600 : 400 }}>{label}</span>
        </span>
      )}
    </NavLink>
  )
}
