import { screen } from '@testing-library/react'
import { vi, expect, test, afterEach } from 'vitest'
import { renderWithProviders } from '../test/utils'
import Tarjetas from './Tarjetas'

afterEach(() => vi.restoreAllMocks())

test('muestra el resumen a pagar (ciclo cerrado) como número principal, con el próximo resumen secundario (UX1)', async () => {
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
  // Principal = resumen a pagar = ciclo cerrado 500000 (lo que vence)
  expect(screen.getByText('Resumen a pagar')).toBeInTheDocument()
  expect(screen.getByText('$500.000,00')).toBeInTheDocument()
  // Secundario = próximo resumen = ciclo abierto 80000 + 1 cuota 10000 = 90000
  expect(screen.getByText(/\$90\.000,00/)).toBeInTheDocument()
  expect(screen.getByText(/cierra 03\/07/)).toBeInTheDocument()
  // la deuda total (185000) no aparece como número
  expect(screen.queryByText('$185.000,00')).not.toBeInTheDocument()
})

test('muestra $0 a pagar cuando no hay resumen cerrado', async () => {
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
  // Sin resumen cerrado → mensaje amable como principal; próximo resumen $0
  expect(screen.getByText('Sin resumen pendiente 🎉')).toBeInTheDocument()
  expect(screen.getByText(/\$0,00/)).toBeInTheDocument()
  expect(screen.getByText(/cargá cierre y vencimiento/)).toBeInTheDocument()
})
