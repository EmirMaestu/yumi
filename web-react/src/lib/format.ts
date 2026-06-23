type Currency = 'ARS' | 'USD' | 'EUR'

const SYMBOL: Record<Currency, string> = { ARS: '$', USD: 'US$', EUR: '€' }
const grouper = new Intl.NumberFormat('es-AR', { maximumFractionDigits: 0 })
const MESES = [
  'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
  'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre',
]

export function formatMoney(amount: number, currency: Currency = 'ARS'): string {
  const rounded = Math.round(amount)
  const sign = rounded < 0 ? '-' : ''
  return `${sign}${SYMBOL[currency]}${grouper.format(Math.abs(rounded))}`
}

export function formatUsdApprox(amountArs: number, blue: number | null): string | null {
  if (!blue || blue <= 0) return null
  return `≈ ${formatMoney(amountArs / blue, 'USD')}`
}

export function formatMonthLabel(year: number, month1to12: number): string {
  return `${MESES[month1to12 - 1]} ${year}`
}
