import { useNavigate } from 'react-router-dom'
import ScopeToggle from './ScopeToggle'

export default function TopBar() {
  const navigate = useNavigate()
  return (
    <header style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '14px 22px' }}>
      <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <span aria-hidden style={{ color: 'var(--color-voltage)', fontWeight: 600, fontSize: 18, letterSpacing: -2 }}>❘❘</span>
        <span aria-label="Yumi" style={{ fontSize: 17, fontWeight: 600, letterSpacing: '-0.01em' }}>
          <span style={{ color: 'var(--color-obsidian-ink)' }}>Yu</span><span style={{ color: 'var(--color-voltage)' }}>mi</span>
        </span>
      </span>
      <span style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <ScopeToggle />
        <button onClick={() => navigate('/buscar')} aria-label="Buscar" style={{ background: 'none', border: 'none', cursor: 'pointer' }}>
          <i className="ti ti-search" style={{ fontSize: 20, color: 'var(--color-obsidian-ink)' }} aria-hidden />
        </button>
      </span>
    </header>
  )
}
