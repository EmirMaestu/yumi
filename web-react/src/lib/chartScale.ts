// Escala "linda" para ejes: redondea el máximo a 1/2/5×10^n y devuelve 4 intervalos
// (5 ticks incluyendo 0). Ej: niceScale(8734) → { max: 10000, ticks: [0,2500,5000,7500,10000] }.
export function niceScale(value: number): { max: number; ticks: number[] } {
  if (value <= 0) return { max: 0, ticks: [0] }
  const pow = Math.pow(10, Math.floor(Math.log10(value)))
  const frac = value / pow
  const niceFrac = frac <= 1 ? 1 : frac <= 2 ? 2 : frac <= 5 ? 5 : 10
  const max = niceFrac * pow
  const step = max / 4
  return { max, ticks: [0, step, 2 * step, 3 * step, max] }
}
