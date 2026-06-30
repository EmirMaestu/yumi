import { type CSSProperties } from 'react'

// Indicador compacto de visibilidad. shared=1 → "Todos"; si no, share_count personas.
export default function ShareBadge({ shared, count }: { shared?: number; count?: number }) {
  const label = shared ? 'Todos' : count && count > 0 ? `${count} ${count === 1 ? 'persona' : 'personas'}` : null
  if (!label) return null
  return (
    <span style={badge}>
      <i className="ti ti-users" style={{ fontSize: 12 }} aria-hidden />
      {label}
    </span>
  )
}

const badge: CSSProperties = {
  display: 'inline-flex', alignItems: 'center', gap: 4,
  fontSize: 11, padding: '2px 8px', borderRadius: 9999,
  background: 'var(--color-mist)', color: 'var(--color-sage)', fontWeight: 500,
}
