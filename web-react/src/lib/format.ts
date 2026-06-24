type Currency = 'ARS' | 'USD' | 'EUR'

const SYMBOL: Record<Currency, string> = { ARS: '$', USD: 'US$', EUR: '€' }
const formatter = new Intl.NumberFormat('es-AR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
const MESES = [
  'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
  'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre',
]

export function formatMoney(amount: number, currency: Currency = 'ARS'): string {
  const sign = amount < 0 ? '-' : ''
  return `${sign}${SYMBOL[currency]}${formatter.format(Math.abs(amount))}`
}

export function formatUsdApprox(amountArs: number, blue: number | null): string | null {
  if (!blue || blue <= 0) return null
  return `≈ ${formatMoney(amountArs / blue, 'USD')}`
}

export function formatMonthLabel(year: number, month1to12: number): string {
  return `${MESES[month1to12 - 1]} ${year}`
}

// El bot a veces guarda el texto del recordatorio como "En 2880 min: Turno…".
// Lo limpiamos para mostrar el contenido (la hora se muestra aparte).
export function cleanReminderText(text: string): string {
  const cleaned = (text || '').replace(/^en\s+\d+\s*(min(?:utos)?|h(?:s|oras?)?|d(?:[ií]as?)?)\b\s*:?\s*/i, '').trim()
  return cleaned || text
}
