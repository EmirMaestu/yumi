import { describe, it, expect } from 'vitest'
import { parseAmount } from './parseAmount'

describe('parseAmount es-AR', () => {
  it.each([
    ['1,50', 1.5], ['1500', 1500], ['1.234,56', 1234.56],
    ['1.234', 1234],        // punto como miles (patrón 1-3 dígitos + grupos de 3)
    ['1234.56', 1234.56],   // punto decimal simple se respeta
    ['1,234.56', 1234.56],  // formato en-US también aceptado
    [' 12 500,10 ', 12500.1],
  ])('parsea %s → %d', (raw, expected) => expect(parseAmount(raw)).toBeCloseTo(expected as number))
  it('devuelve NaN para basura', () => { expect(parseAmount('abc')).toBeNaN(); expect(parseAmount('')).toBeNaN() })
})
