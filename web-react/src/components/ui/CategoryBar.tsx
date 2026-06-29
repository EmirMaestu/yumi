import { Link } from 'react-router-dom'
import { formatMoney } from '../../lib/format'

// Si recibe `to`, la barra se vuelve clickeable (ej. → Movimientos filtrado por categoría).
export default function CategoryBar({ label, total, max, to }: { label: string; total: number; max: number; to?: string }) {
  const pct = max > 0 ? Math.min(100, Math.round((total / max) * 100)) : 0
  const inner = (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 11 }}>
      <span style={{ fontSize: 13, width: 90 }}>{label}</span>
      <span style={{ flex: 1, height: 6, background: 'var(--color-mist)', borderRadius: 5, overflow: 'hidden' }}>
        <span style={{ display: 'block', width: `${pct}%`, height: '100%', background: 'var(--color-bark)' }} />
      </span>
      <span style={{ fontSize: 12.5, color: 'var(--color-sage)', width: 70, textAlign: 'right' }}>{formatMoney(total)}</span>
    </div>
  )
  if (to) return <Link to={to} style={{ textDecoration: 'none', color: 'inherit', display: 'block' }}>{inner}</Link>
  return inner
}
