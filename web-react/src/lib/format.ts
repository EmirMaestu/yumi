import { type Currency, CURRENCY_SYMBOL } from './currencies'

const SYMBOL = CURRENCY_SYMBOL
const formatter = new Intl.NumberFormat('es-AR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
const MESES = [
  'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
  'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre',
]

export function formatMoney(amount: number, currency: Currency = 'ARS'): string {
  const sign = amount < 0 ? '-' : ''
  const sym = SYMBOL[currency] ?? `${currency} `  // fallback: moneda desconocida → muestra el código
  return `${sign}${sym}${formatter.format(Math.abs(amount))}`
}

export function formatUsdApprox(amountArs: number, blue: number | null): string | null {
  if (!blue || blue <= 0) return null
  return `≈ ${formatMoney(amountArs / blue, 'USD')}`
}

export function formatMonthLabel(year: number, month1to12: number): string {
  return `${MESES[month1to12 - 1]} ${year}`
}

// 'YYYY-MM' → 'jun' (mes corto, para ejes de gráficos).
export function formatMonthShort(ym: string): string {
  const m = Number(ym.slice(5, 7))
  return (MESES[m - 1] ?? '').slice(0, 3)
}

// Fecha local de hoy como 'YYYY-MM-DD' (para <input type="date">). No usa
// toISOString() porque eso da UTC y cerca de medianoche cambia de día.
export function todayISODate(): string {
  const d = new Date()
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

// Compone una fecha 'YYYY-MM-DD' a ISO al mediodía local ('YYYY-MM-DDT12:00'),
// para que el guardado no salte de día por zona horaria.
export function dateToNoonISO(date: string): string {
  return `${date.slice(0, 10)}T12:00`
}

// Encabezado de día para agrupar movimientos: "Hoy" / "Ayer" / "12 de junio".
export function formatDayHeader(isoDate: string): string {
  const d = isoDate.slice(0, 10)
  if (d === todayISODate()) return 'Hoy'
  const y = new Date()
  y.setDate(y.getDate() - 1)
  const pad = (n: number) => String(n).padStart(2, '0')
  const ayer = `${y.getFullYear()}-${pad(y.getMonth() + 1)}-${pad(y.getDate())}`
  if (d === ayer) return 'Ayer'
  const [, m, day] = d.split('-')
  return `${Number(day)} de ${MESES[Number(m) - 1]}`
}

// El bot a veces guarda el texto del recordatorio como "En 2880 min: Turno…".
// Lo limpiamos para mostrar el contenido (la hora se muestra aparte).
export function cleanReminderText(text: string): string {
  const cleaned = (text || '').replace(/^en\s+\d+\s*(min(?:utos)?|h(?:s|oras?)?|d(?:[ií]as?)?)\b\s*:?\s*/i, '').trim()
  return cleaned || text
}
