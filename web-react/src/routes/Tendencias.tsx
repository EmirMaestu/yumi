import { useState } from 'react'
import { useMonthlyTrend, useCategoryTrend } from '../hooks/useTrends'
import { Money } from '../lib/privacy'
import Card from '../components/ui/Card'
import BackButton from '../components/ui/BackButton'
import EmptyState from '../components/ui/EmptyState'
import { MovimientosSkeleton } from '../components/ui/skeletons'
import BarsMonthly from '../components/charts/BarsMonthly'
import LinesByCategory from '../components/charts/LinesByCategory'

export default function Tendencias() {
  const [months, setMonths] = useState<6 | 12>(6)
  const monthly = useMonthlyTrend(months)
  const category = useCategoryTrend(months)

  if (monthly.isLoading || category.isLoading) return <MovimientosSkeleton />

  const m = monthly.data
  const c = category.data
  const gastoArs = m?.series.gasto?.ARS ?? []
  const ingresoArs = m?.series.ingreso?.ARS ?? []
  const hasData = (m?.labels.length ?? 0) > 0 && (gastoArs.some((v) => v > 0) || ingresoArs.some((v) => v > 0))

  // Tabla comparativa: último mes vs anterior, por categoría, con Δ%.
  const catRows = Object.entries(c?.series ?? {})
    .map(([cat, vals]) => {
      const last = vals[vals.length - 1] ?? 0
      const prev = vals[vals.length - 2] ?? 0
      const delta = prev > 0 ? ((last - prev) / prev) * 100 : (last > 0 ? 100 : 0)
      return { cat, last, prev, delta, total: vals.reduce((a, b) => a + b, 0) }
    })
    .sort((a, b) => b.total - a.total)
    .slice(0, 8)

  return (
    <div style={{ padding: '14px 18px 24px', display: 'grid', gap: 16 }}>
      <div style={{ display: 'flex', alignItems: 'center' }}>
        <BackButton />
        <div className="cap" style={{ flex: 1 }}>Tendencias</div>
        <div style={{ display: 'flex', gap: 6 }}>
          {[6, 12].map((mm) => (
            <button key={mm} onClick={() => setMonths(mm as 6 | 12)}
              style={mm === months ? toggleOn : toggleOff}>{mm}m</button>
          ))}
        </div>
      </div>

      {!hasData
        ? <EmptyState>Todavía no hay suficientes movimientos para mostrar tendencias.</EmptyState>
        : (
          <>
            <Card>
              <div className="cap" style={{ marginBottom: 10 }}>Gastos e ingresos por mes</div>
              <BarsMonthly labels={m!.labels} gasto={gastoArs} ingreso={ingresoArs} />
              <div style={{ display: 'flex', gap: 14, marginTop: 6, fontSize: 11, color: 'var(--color-sage)' }}>
                <span><span style={{ display: 'inline-block', width: 9, height: 9, borderRadius: 2, background: 'var(--color-obsidian-ink)', marginRight: 4 }} />Gastos</span>
                <span><span style={{ display: 'inline-block', width: 9, height: 9, borderRadius: 2, background: 'var(--color-voltage)', marginRight: 4 }} />Ingresos</span>
              </div>
            </Card>

            {Object.keys(c?.series ?? {}).length > 0 && (
              <Card>
                <div className="cap" style={{ marginBottom: 10 }}>Por categoría</div>
                <LinesByCategory labels={c!.labels} series={c!.series} />
              </Card>
            )}

            {catRows.length > 0 && (
              <Card>
                <div className="cap" style={{ marginBottom: 10 }}>Este mes vs anterior</div>
                <div style={{ display: 'grid', gap: 8 }}>
                  {catRows.map((r) => (
                    <div key={r.cat} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', fontSize: 13 }}>
                      <span style={{ flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{r.cat}</span>
                      <span style={{ marginRight: 10 }}><Money value={r.last} /></span>
                      <span style={{ fontSize: 12, color: r.delta > 0 ? 'var(--color-error)' : '#3b6d11', minWidth: 56, textAlign: 'right' }}>
                        {r.delta > 0 ? '▲' : r.delta < 0 ? '▼' : '='} {Math.abs(Math.round(r.delta))}%
                      </span>
                    </div>
                  ))}
                </div>
              </Card>
            )}
          </>
        )}

      <div style={{ fontSize: 11, color: 'var(--color-sage)', textAlign: 'center' }}>
        Solo movimientos en ARS. No incluye transferencias ni ajustes.
      </div>
    </div>
  )
}

const toggleBase: React.CSSProperties = { borderRadius: 8, padding: '5px 12px', fontSize: 13, cursor: 'pointer', border: '1px solid var(--color-mist)' }
const toggleOn: React.CSSProperties = { ...toggleBase, background: 'var(--color-voltage)', color: 'var(--voltage-on-dark)', border: 'none', fontWeight: 500 }
const toggleOff: React.CSSProperties = { ...toggleBase, background: 'transparent', color: 'var(--color-sage)' }
