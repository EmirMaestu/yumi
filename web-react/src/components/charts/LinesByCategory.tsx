import { useState } from 'react'
import { niceScale } from '../../lib/chartScale'
import { paletteColor } from '../../lib/palette'
import { formatMonthShort } from '../../lib/format'

// Líneas por categoría (máx 6, colores de la paleta D11). Leyenda clickeable para
// ocultar series. SVG fluido, sin animaciones. role="img" + aria-label.
export default function LinesByCategory({ labels, series }: {
  labels: string[]
  series: Record<string, number[]>
}) {
  // top 6 por total
  const cats = Object.entries(series)
    .map(([cat, vals]) => ({ cat, vals, total: vals.reduce((a, b) => a + b, 0) }))
    .sort((a, b) => b.total - a.total)
    .slice(0, 6)

  const [hidden, setHidden] = useState<Set<string>>(new Set())
  const toggle = (cat: string) => setHidden((prev) => {
    const next = new Set(prev); next.has(cat) ? next.delete(cat) : next.add(cat); return next
  })

  const W = 640, H = 200
  const padL = 8, padR = 8, padB = 22, padT = 8
  const chartW = W - padL - padR
  const chartH = H - padT - padB
  const n = Math.max(1, labels.length)
  const visible = cats.filter((c) => !hidden.has(c.cat))
  const maxVal = Math.max(1, ...visible.flatMap((c) => c.vals))
  const { max } = niceScale(maxVal)
  const x = (i: number) => padL + (n === 1 ? chartW / 2 : (chartW * i) / (n - 1))
  const y = (v: number) => padT + chartH - (v / (max || 1)) * chartH

  return (
    <div>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img"
        aria-label={`Gasto por categoría en ${n} meses`} style={{ display: 'block' }}>
        <line x1={padL} y1={padT + chartH} x2={W - padR} y2={padT + chartH} stroke="var(--color-mist)" />
        {cats.map((c, i) => {
          if (hidden.has(c.cat)) return null
          const pts = c.vals.map((v, j) => `${x(j)},${y(v)}`).join(' ')
          return <polyline key={c.cat} points={pts} fill="none" stroke={paletteColor(i)} strokeWidth={2} strokeLinejoin="round" />
        })}
        {labels.map((lab, i) => (
          <text key={lab} x={x(i)} y={H - 6} textAnchor="middle" fontSize={10} fill="var(--color-sage)">{formatMonthShort(lab)}</text>
        ))}
      </svg>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 8 }}>
        {cats.map((c, i) => (
          <button key={c.cat} onClick={() => toggle(c.cat)}
            style={{ display: 'inline-flex', alignItems: 'center', gap: 5, background: 'transparent', border: 'none', cursor: 'pointer', fontSize: 12, opacity: hidden.has(c.cat) ? 0.4 : 1, color: 'var(--color-obsidian-ink)' }}>
            <span style={{ width: 10, height: 10, borderRadius: 3, background: paletteColor(i), display: 'inline-block' }} />
            {c.cat}
          </button>
        ))}
      </div>
    </div>
  )
}
