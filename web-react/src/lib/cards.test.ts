import { describe, expect, test } from 'vitest'
import { type Recurring, type VencimientoCard } from './types'
import { consumos, enCuotas, deudaTotal, cuotaActual, cicloArs, aPagarCard, aPagarTotal, recurrenteMensual, cicloEnCurso } from './cards'

const card = { balances: [{ currency: 'ARS' as const, balance: -100000 }] }

function rec(p: Partial<Recurring> & Pick<Recurring, 'id' | 'account_id' | 'amount'>): Recurring {
  return { description: 'x', currency: 'ARS', next_occurrence: '', active: 1, ...p }
}

const recurring: Recurring[] = [
  rec({ id: 1, account_id: 1, amount: 20000, total_installments: 6, installments_fired: 3 }),          // activa
  rec({ id: 2, account_id: 1, amount: 10000, total_installments: 4, installments_fired: 1, active: 0 }), // PAUSADA
  rec({ id: 3, account_id: 1, amount: 9999 }),                                                          // fijo mensual (sin cuotas)
  rec({ id: 4, account_id: 2, amount: 5000, total_installments: 3, installments_fired: 0 }),            // otra tarjeta
]

describe('modelo de plata de la tarjeta', () => {
  test('consumos = valor absoluto del saldo ARS', () => {
    expect(consumos(card)).toBe(100000)
  })

  test('enCuotas suma lo que falta, incluyendo planes pausados', () => {
    // activa: 20000*(6-3)=60000 ; pausada: 10000*(4-1)=30000 ; fijo: no cuenta
    expect(enCuotas(1, recurring)).toBe(90000)
  })

  test('enCuotas no mezcla otras tarjetas', () => {
    expect(enCuotas(2, recurring)).toBe(15000) // 5000*(3-0)
  })

  test('deudaTotal = consumos + cuotas por venir', () => {
    expect(deudaTotal(1, card, recurring)).toBe(190000) // 100000 + 90000
  })

  test('cuotaActual = pagadas + 1 (con tope en el total)', () => {
    expect(cuotaActual({ installments_fired: 3, total_installments: 6 })).toBe(4)
    expect(cuotaActual({ installments_fired: 0, total_installments: 6 })).toBe(1)
    expect(cuotaActual({ installments_fired: 6, total_installments: 6 })).toBe(6) // terminada, no se pasa
    expect(cuotaActual({ installments_fired: null, total_installments: null })).toBe(0)
  })

  test('cicloArs suma solo ARS', () => {
    expect(cicloArs([{ currency: 'ARS', total: 5000 }, { currency: 'USD', total: 9 }])).toBe(5000)
  })

  test('a pagar ahora = ciclo cerrado (lo que vence)', () => {
    const v: VencimientoCard = {
      account_id: 1, account_name: 'Visa',
      ciclo_cerrado: [{ currency: 'ARS', total: 45000 }],
      ciclo_abierto: [{ currency: 'ARS', total: 20000 }],
    }
    expect(aPagarCard(v)).toBe(45000)        // cerrado, no abierto
    expect(aPagarTotal([v, v])).toBe(90000)  // suma de tarjetas
  })

  test('recurrenteMensual = una cuota por plan activo + fijos (excluye pausados)', () => {
    // id1 activa $20000 + id3 fijo $9999 ; id2 PAUSADA no cuenta este mes
    expect(recurrenteMensual(1, recurring)).toBe(29999)
    expect(recurrenteMensual(2, recurring)).toBe(5000) // otra tarjeta, una cuota
  })

  test('cicloEnCurso = ciclo abierto (compras) + recurrente mensual (cuotas)', () => {
    const v: VencimientoCard = {
      account_id: 1, account_name: 'Visa',
      ciclo_cerrado: [], ciclo_abierto: [{ currency: 'ARS', total: 5000 }],
    }
    expect(cicloEnCurso(1, v, recurring)).toBe(34999) // 5000 + 29999
    // sin transacciones en el ciclo, igual muestra las cuotas (no $0)
    expect(cicloEnCurso(1, undefined, recurring)).toBe(29999)
  })
})
