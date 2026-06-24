import { formatMoney, formatUsdApprox, formatMonthLabel } from './format'

test('formatMoney ARS: miles con punto, 2 decimales', () => {
  expect(formatMoney(1140000)).toBe('$1.140.000,00')
  expect(formatMoney(0)).toBe('$0,00')
  expect(formatMoney(5400.5)).toBe('$5.400,50')
  expect(formatMoney(-207000)).toBe('-$207.000,00')
})

test('formatMoney USD y EUR con prefijo propio', () => {
  expect(formatMoney(2066, 'USD')).toBe('US$2.066,00')
  expect(formatMoney(50, 'EUR')).toBe('€50,00')
})

test('formatUsdApprox usa el blue; null si no hay rate', () => {
  expect(formatUsdApprox(2480500, 1200)).toBe('≈ US$2.067,08')
  expect(formatUsdApprox(2480500, 0)).toBeNull()
  expect(formatUsdApprox(2480500, null)).toBeNull()
})

test('formatMonthLabel devuelve mes y año en es-AR', () => {
  expect(formatMonthLabel(2026, 6)).toBe('junio 2026')
})
