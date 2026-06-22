import ScopeToggle from './ScopeToggle'

export default function TopBar({ onMenu }: { onMenu: () => void }) {
  return (
    <header style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '14px 22px' }}>
      <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <span style={{ color: 'var(--color-voltage)', fontWeight: 600, fontSize: 18, letterSpacing: -2 }}>❘❘</span>
        <span className="cap" style={{ color: 'var(--color-obsidian-ink)', letterSpacing: '0.04em', fontSize: 12 }}>[ tu marca ]</span>
      </span>
      <span style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <ScopeToggle />
        <button onClick={onMenu} aria-label="Menú" style={{ background: 'none', border: 'none', cursor: 'pointer' }}>
          <i className="ti ti-menu-2" style={{ fontSize: 20, color: 'var(--color-obsidian-ink)' }} aria-hidden />
        </button>
      </span>
    </header>
  )
}
