import { describe, it, expect } from 'vitest'
import { niceScale } from './chartScale'

describe('niceScale', () => {
  it('redondea a un máximo lindo con 4 intervalos', () => {
    expect(niceScale(8734)).toEqual({ max: 10000, ticks: [0, 2500, 5000, 7500, 10000] })
  })
  it('elige 1/2/5×10^n según la fracción', () => {
    expect(niceScale(1200).max).toBe(2000)   // 1.2 → 2
    expect(niceScale(3400).max).toBe(5000)   // 3.4 → 5
    expect(niceScale(600).max).toBe(1000)    // 6 → 10
    expect(niceScale(950).max).toBe(1000)    // 0.95 → 1
  })
  it('maneja 0 y negativos sin romper', () => {
    expect(niceScale(0)).toEqual({ max: 0, ticks: [0] })
    expect(niceScale(-5)).toEqual({ max: 0, ticks: [0] })
  })
})
