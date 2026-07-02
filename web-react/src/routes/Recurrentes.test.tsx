import { describe, it, expect } from 'vitest'
import { recurringToFormInitial } from './Recurrentes'
import { type Recurring } from '../lib/types'

const base: Recurring = {
  id: 1, description: 'Netflix', amount: 5000, currency: 'ARS',
  account_id: 7, next_occurrence: '2026-07-15', active: 1,
  day_of_month: 15, total_installments: null, installments_fired: null,
}

describe('recurringToFormInitial (BF1)', () => {
  it('preserva day_of_month del ítem, no lo pisa con 1', () => {
    expect(recurringToFormInitial(base).day_of_month).toBe(15)
  })

  it('cae a 1 solo cuando el ítem no tiene day_of_month', () => {
    expect(recurringToFormInitial({ ...base, day_of_month: null }).day_of_month).toBe(1)
  })

  it('mapea el resto de los campos del ítem real', () => {
    const f = recurringToFormInitial({ ...base, amount: 1234, total_installments: 6, installments_fired: 2 })
    expect(f.description).toBe('Netflix')
    expect(f.amount).toBe(1234)
    expect(f.account_id).toBe('7')
    expect(f.total_installments).toBe(6)
    expect(f.installments_fired).toBe(2)
  })
})
