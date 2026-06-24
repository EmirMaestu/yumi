import { screen } from '@testing-library/react'
import { vi, expect, test, afterEach } from 'vitest'
import { renderWithProviders } from '../test/utils'
import Tarjetas from './Tarjetas'

afterEach(() => vi.restoreAllMocks())

test('muestra una tarjeta con la deuda (saldo) como número principal', async () => {
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
    return Promise.resolve(new Response('[]', { status: 200 }))
  }))
  renderWithProviders(<Tarjetas />)
  expect(await screen.findByText('Visa Galicia')).toBeInTheDocument()
  // Primary number is now the ARS balance (deuda)
  expect(screen.getByText('-$145.000,00')).toBeInTheDocument()
  // Label shows "Deuda"
  expect(screen.getByText('Deuda')).toBeInTheDocument()
})
