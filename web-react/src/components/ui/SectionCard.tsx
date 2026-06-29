import { Link } from 'react-router-dom'
import Card from './Card'

// Card-resumen de una sección: se clickea y lleva a su pantalla.
// Se usa en Inicio (Hábitos/Listas/Notas) y en Finanzas (Movimientos/Tarjetas/…).
export default function SectionCard({ to, icon, label, summary }: { to: string; icon: string; label: string; summary: string }) {
  return (
    <div style={{ padding: '0 18px 12px' }}>
      <Link to={to} style={{ textDecoration: 'none', color: 'inherit' }}>
        <Card>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <i className={`ti ${icon}`} style={{ fontSize: 16, color: 'var(--color-sage)' }} aria-hidden />
              <span className="cap">{label}</span>
            </div>
            <i className="ti ti-chevron-right" style={{ fontSize: 16, color: 'var(--color-sage)' }} aria-hidden />
          </div>
          <div style={{ fontSize: 14, color: 'var(--color-sage)', marginTop: 8 }}>{summary}</div>
        </Card>
      </Link>
    </div>
  )
}
