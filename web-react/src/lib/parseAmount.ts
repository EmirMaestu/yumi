// Regla es-AR-first: coma = decimal. Punto = miles cuando el patrón es
// 1-3 dígitos + grupos de 3. Devuelve NaN si no es un número parseable.
export function parseAmount(raw: string): number {
  const s = String(raw).trim().replace(/\s/g, '')
  if (!s) return NaN
  const lastComma = s.lastIndexOf(','), lastDot = s.lastIndexOf('.')
  let norm: string
  if (lastComma > -1 && lastDot > -1) {
    norm = lastComma > lastDot ? s.replace(/\./g, '').replace(',', '.') : s.replace(/,/g, '')
  } else if (lastComma > -1) {
    norm = s.replace(/\./g, '').replace(',', '.')
  } else if (lastDot > -1 && /^\d{1,3}(\.\d{3})+$/.test(s)) {
    norm = s.replace(/\./g, '')
  } else {
    norm = s
  }
  return Number(norm)
}
