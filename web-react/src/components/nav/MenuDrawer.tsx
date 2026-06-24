import { Link } from 'react-router-dom'
import { MENU_LINKS } from './navItems'

export default function MenuDrawer({ open, onClose }: { open: boolean; onClose: () => void }) {
  if (!open) return null
  return (
    <div
      onClick={onClose}
      style={{ position: 'fixed', inset: 0, zIndex: 60, background: 'rgba(18,22,19,0.45)', display: 'flex', justifyContent: 'flex-end' }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{ width: '78%', maxWidth: 320, height: '100%', background: 'var(--color-linen)', padding: 24, display: 'grid', gap: 16, alignContent: 'start', overflowY: 'auto' }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span className="cap">Menú</span>
          <button onClick={onClose} aria-label="Cerrar" style={{ background: 'none', border: 'none', cursor: 'pointer' }}>
            <i className="ti ti-x" style={{ fontSize: 20 }} aria-hidden />
          </button>
        </div>
        {MENU_LINKS.map((section, si) => (
          <div key={si}>
            {section.title && (
              <div className="cap" style={{ fontSize: 10, letterSpacing: '0.08em', color: 'var(--color-sage)', marginBottom: 8 }}>
                {section.title}
              </div>
            )}
            <div style={{ display: 'grid', gap: 12 }}>
              {section.links.map((l) => (
                <Link key={l.to} to={l.to} onClick={onClose} style={{ color: 'var(--color-obsidian-ink)', textDecoration: 'none', fontSize: 16 }}>{l.label}</Link>
              ))}
            </div>
            {si < MENU_LINKS.length - 1 && (
              <div style={{ height: 1, background: 'var(--color-mist)', marginTop: 16 }} />
            )}
          </div>
        ))}
        <a href="/legacy/" style={{ color: 'var(--color-sage)', fontSize: 14, textDecoration: 'none', marginTop: 8 }}>Dashboard viejo →</a>
      </div>
    </div>
  )
}
