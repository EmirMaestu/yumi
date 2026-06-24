import { screen } from '@testing-library/react'
import { vi, expect, test, afterEach } from 'vitest'
import { renderWithProviders } from '../test/utils'
import Tarjetas from './Tarjetas'

afterEach(() => vi.restoreAllMocks())

test('muestra una tarjeta con la deuda total (consumos + cuotas) como número principal', async () => {
  vi.stubGlobal('fetch', vi.fn((url: string) => {
    const u = String(url)
    // useAccountsWithBalances fetches /api/overview → { accounts: [...] }
    if (u.includes('/api/overview') && !u.includes('/api/overview2')) {
      return Promise.resolve(new Response(JSON.stringify({
        accounts: [{ id: 1, name: 'Visa Galicia', type: 'credito', active: 1, balances: [{ currency: 'ARS', balance: -145000 }] }],
      }), { status: 200 }))
    }
    if (u.includes('/api/vencimientos')) {
      return Promise.resolve(new Response(JSON.stringify([{
        account_id: 1,
        account_name: 'Visa Galicia',
        next_due: '2026-07-10',
        next_closing: '2026-07-03',
        ciclo_cerrado: [{ currency: 'ARS', total: 500000 }],
        ciclo_abierto: [{ currency: 'ARS', total: 80000 }],
      }]), { status: 200 }))
    }
    if (u.includes('/api/recurring')) {
      // 1 installment plan: 6 cuotas total, 2 fired, $10000 each → enCuotas = 4 * 10000 = 40000
      return Promise.resolve(new Response(JSON.stringify([
        { id: 10, description: 'Netflix cuotas', amount: 10000, currency: 'ARS', account_id: 1, next_occurrence: '2026-07-01', active: 1, total_installments: 6, installments_fired: 2 },
      ]), { status: 200 }))
    }
    return Promise.resolve(new Response('[]', { status: 200 }))
  }))
  renderWithProviders(<Tarjetas />)
  expect(await screen.findByText('Visa Galicia')).toBeInTheDocument()
  // deudaTotal = abs(-145000) + (6-2)*10000 = 145000 + 40000 = 185000
  expect(screen.getByText('$185.000,00')).toBeInTheDocument()
  // Label shows "Deuda"
  expect(screen.getByText('Deuda')).toBeInTheDocument()
  // Breakdown line
  expect(screen.getByText(/Consumos.*En cuotas/)).toBeInTheDocument()
})

test('muestra deuda igual a consumos cuando no hay cuotas pendientes', async () => {
  vi.stubGlobal('fetch', vi.fn((url: string) => {
    const u = String(url)
    if (u.includes('/api/overview') && !u.includes('/api/overview2')) {
      return Promise.resolve(new Response(JSON.stringify({
        accounts: [{ id: 2, name: 'Mastercard', type: 'credito', active: 1, balances: [{ currency: 'ARS', balance: -60000 }] }],
      }), { status: 200 }))
    }
    if (u.includes('/api/vencimientos')) {
      return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }))
    }
    if (u.includes('/api/recurring')) {
      return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }))
    }
    return Promise.resolve(new Response('[]', { status: 200 }))
  }))
  renderWithProviders(<Tarjetas />)
  expect(await screen.findByText('Mastercard')).toBeInTheDocument()
  // deudaTotal = abs(-60000) + 0 = 60000
  expect(screen.getByText('$60.000,00')).toBeInTheDocument()
})
