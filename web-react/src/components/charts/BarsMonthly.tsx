import { niceScale } from '../../lib/chartScale'
import { formatMonthShort, formatMoney } from '../../lib/format'

// Barras verticales por mes (hasta 12). Par gasto/ingreso opcional. SVG fluido
// con viewBox; tooltip nativo via <title>. Sin animaciones (D3).
export default function BarsMonthly({ labels, gasto, ingreso }: {
  labels: string[]
  gasto: number[]
  ingreso?: number[]
}) {
  const W = 640, H = 180
  const padL = 8, padR = 8, padB = 22, padT = 8
  const chartW = W - padL - padR
  const chartH = H - padT - padB
  const n = labels.length || 1
  const maxVal = Math.max(1, ...gasto, ...(ingreso ?? []))
  const { max } = niceScale(maxVal)
  const slot = chartW / n
  const hasIngreso = !!ingreso
  const barW = hasIngreso ? Math.min(18, slot * 0.28) : Math.min(26, slot * 0.5)
  const y = (v: number) => padT + chartH - (v / (max || 1)) * chartH

  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img"
      aria-label={`Gastos${hasIngreso ? ' e ingresos' : ''} por mes, ${n} meses`} style={{ display: 'block' }}>
      {/* baseline */}
      <line x1={padL} y1={padT + chartH} x2={W - padR} y2={padT + chartH} stroke="var(--color-mist)" />
      {labels.map((lab, i) => {
        const cx = padL + slot * i + slot / 2
        const g = gasto[i] ?? 0
        const ing = ingreso?.[i] ?? 0
        const gx = hasIngreso ? cx - barW - 1 : cx - barW / 2
        const ix = cx + 1
        return (
          <g key={lab}>
            <rect x={gx} y={y(g)} width={barW} height={padT + chartH - y(g)} fill="var(--color-obsidian-ink)" rx={2}>
              <title>{`${formatMonthShort(lab)}: gasto ${formatMoney(g)}`}</title>
            </rect>
            {hasIngreso && (
              <rect x={ix} y={y(ing)} width={barW} height={padT + chartH - y(ing)} fill="var(--color-voltage)" rx={2}>
                <title>{`${formatMonthShort(lab)}: ingreso ${formatMoney(ing)}`}</title>
              </rect>
            )}
            <text x={cx} y={H - 6} textAnchor="middle" fontSize={10} fill="var(--color-sage)">{formatMonthShort(lab)}</text>
          </g>
        )
      })}
    </svg>
  )
}
