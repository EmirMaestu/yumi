import { Link, useParams } from 'react-router-dom'
import { useStatements, useStatement } from '../hooks/useStatements'
import { formatMonthLabel } from '../lib/format'
import { Money } from '../lib/privacy'
import Card from '../components/ui/Card'
import BackButton from '../components/ui/BackButton'
import EmptyState from '../components/ui/EmptyState'
import { MovimientosSkeleton } from '../components/ui/skeletons'

// Lista de resúmenes mensuales anteriores.
export default function Resumenes() {
  const { data, isLoading } = useStatements()
  const now = new Date()
  const py = now.getMonth() === 0 ? now.getFullYear() - 1 : now.getFullYear()
  const pm = now.getMonth() === 0 ? 12 : now.getMonth() // mes anterior (1-12)

  if (isLoading) return <MovimientosSkeleton />
  const items = data ?? []

  return (
    <div style={{ padding: '14px 18px 24px', display: 'grid', gap: 12 }}>
      <div style={{ display: 'flex', alignItems: 'center' }}>
        <BackButton />
        <div className="cap" style={{ flex: 1 }}>Resúmenes anteriores</div>
        <Link to={`/resumenes/${py}/${pm}`} style={{ fontSize: 13, color: 'var(--color-sage)', textDecoration: 'none' }}>Ver mes anterior →</Link>
      </div>

      {items.length === 0
        ? <EmptyState>Todavía no hay resúmenes cerrados. Tocá "Ver mes anterior" para generar el del último mes.</EmptyState>
        : items.map((s) => (
          <Link key={`${s.year}-${s.month}`} to={`/resumenes/${s.year}/${s.month}`} style={{ textDecoration: 'none', color: 'inherit' }}>
            <Card style={{ cursor: 'pointer' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
                <span style={{ fontSize: 15, fontWeight: 500, textTransform: 'capitalize' }}>{formatMonthLabel(s.year, s.month)}</span>
                <span className="num-serif" style={{ fontSize: 18 }}><Money value={s.gasto_total} /></span>
              </div>
              {s.vs_prev_pct != null && (
                <div style={{ fontSize: 12, color: s.vs_prev_pct > 0 ? 'var(--color-error)' : '#3b6d11', marginTop: 2 }}>
                  {s.vs_prev_pct > 0 ? '▲' : '▼'} {Math.abs(Math.round(s.vs_prev_pct))}% vs mes anterior
                </div>
              )}
            </Card>
          </Link>
        ))}
    </div>
  )
}

// Detalle de un resumen mensual.
export function ResumenDetalle() {
  const { year, month } = useParams()
  const y = Number(year), m = Number(month)
  const { data, isLoading, isError } = useStatement(y, m)

  if (isLoading) return <MovimientosSkeleton />
  if (isError || !data) return (
    <div style={{ padding: 18 }}>
      <Link to="/resumenes" style={{ fontSize: 13, color: 'var(--color-sage)' }}>← Resúmenes</Link>
      <EmptyState>Ese mes todavía no cerró o no hay datos.</EmptyState>
    </div>
  )

  const maxCat = Math.max(1, ...data.por_categoria.map((c) => c.total))

  return (
    <div style={{ padding: '14px 18px 24px', display: 'grid', gap: 16 }}>
      <div>
        <Link to="/resumenes" style={{ fontSize: 13, color: 'var(--color-sage)', textDecoration: 'none' }}>← Resúmenes</Link>
        <h1 style={{ fontSize: 22, fontWeight: 600, margin: '8px 0 0', textTransform: 'capitalize' }}>{formatMonthLabel(y, m)}</h1>
      </div>

      <Card>
        <div style={{ display: 'flex', gap: 20 }}>
          <div>
            <div className="cap">Gastos</div>
            <div className="num-serif" style={{ fontSize: 26 }}><Money value={data.gasto_total} /></div>
          </div>
          <div>
            <div className="cap">Ingresos</div>
            <div className="num-serif" style={{ fontSize: 26 }}><Money value={data.ingreso_total} /></div>
          </div>
        </div>
        <div style={{ fontSize: 12, color: 'var(--color-sage)', marginTop: 6 }}>{data.n_movimientos} movimientos</div>
      </Card>

      {data.por_categoria.length > 0 && (
        <Card>
          <div className="cap" style={{ marginBottom: 10 }}>Top categorías</div>
          <div style={{ display: 'grid', gap: 8 }}>
            {data.por_categoria.slice(0, 8).map((c) => (
              <div key={c.name}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13, marginBottom: 3 }}>
                  <span>{c.name}</span><span><Money value={c.total} /></span>
                </div>
                <div style={{ height: 6, borderRadius: 4, background: 'var(--color-mist)', overflow: 'hidden' }}>
                  <div style={{ width: `${(c.total / maxCat) * 100}%`, height: '100%', background: 'var(--color-obsidian-ink)' }} />
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}

      {data.por_cuenta.length > 0 && (
        <Card>
          <div className="cap" style={{ marginBottom: 10 }}>Por cuenta</div>
          {data.por_cuenta.map((a) => (
            <div key={a.name} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13, padding: '3px 0' }}>
              <span>{a.name}</span><span style={{ color: a.neto < 0 ? 'var(--color-obsidian-ink)' : '#3b6d11' }}><Money value={a.neto} /></span>
            </div>
          ))}
        </Card>
      )}

      <div style={{ display: 'flex', gap: 8 }}>
        <a href={`/api/export.csv?year=${y}&month=${m}`} download style={btn}>Exportar CSV</a>
        <button onClick={() => window.print()} style={btn}>Imprimir</button>
      </div>
    </div>
  )
}

const btn: React.CSSProperties = { flex: 1, textAlign: 'center', textDecoration: 'none', color: 'var(--color-obsidian-ink)', background: 'transparent', border: '1px solid var(--color-mist)', borderRadius: 10, padding: '11px', fontSize: 13, cursor: 'pointer' }
