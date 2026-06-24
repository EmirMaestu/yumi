import { screen } from '@testing-library/react'
import { vi, expect, test, afterEach } from 'vitest'
import { renderWithProviders } from '../test/utils'
import Cuentas from './Cuentas'
afterEach(() => vi.restoreAllMocks())

test('lista cuentas con saldo (billetera)', async () => {
  vi.stubGlobal('fetch', vi.fn((url: string) => {
    const u = String(url)
    if (u.includes('/api/overview') && !u.includes('/api/overview2')) {
      return Promise.resolve(new Response(JSON.stringify({
        accounts: [{ id: 1, name: 'MP', type: 'billetera', active: 1, balances: [{ currency: 'ARS', balance: 250000 }] }],
      }), { status: 200 }))
    }
    if (u.includes('/api/recurring')) {
      return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }))
    }
    return Promise.resolve(new Response('[]', { status: 200 }))
  }))
  renderWithProviders(<Cuentas />)
  expect(await screen.findByText('MP')).toBeInTheDocument()
  expect(screen.getByText('$250.000,00')).toBeInTheDocument()
})

test('cuenta de crédito muestra deuda total (consumos + cuotas)', async () => {
  vi.stubGlobal('fetch', vi.fn((url: string) => {
    const u = String(url)
    if (u.includes('/api/overview') && !u.includes('/api/overview2')) {
      return Promise.resolve(new Response(JSON.stringify({
        accounts: [{ id: 5, name: 'Visa', type: 'credito', active: 1, balances: [{ currency: 'ARS', balance: -80000 }] }],
      }), { status: 200 }))
    }
    if (u.includes('/api/recurring')) {
      // enCuotas = (3-1)*15000 = 30000
      return Promise.resolve(new Response(JSON.stringify([
        { id: 20, description: 'Compra en cuotas', amount: 15000, currency: 'ARS', account_id: 5, next_occurrence: '2026-07-01', active: 1, total_installments: 3, installments_fired: 1 },
      ]), { status: 200 }))
    }
    return Promise.resolve(new Response('[]', { status: 200 }))
  }))
  renderWithProviders(<Cuentas />)
  expect(await screen.findByText('Visa')).toBeInTheDocument()
  // deudaTotal = abs(-80000) + 30000 = 110000
  expect(screen.getByText('$110.000,00')).toBeInTheDocument()
  // shows "Deuda" label
  expect(screen.getByText('Deuda')).toBeInTheDocument()
  // breakdown line visible
  expect(screen.getByText(/Consumos.*En cuotas/)).toBeInTheDocument()
})
