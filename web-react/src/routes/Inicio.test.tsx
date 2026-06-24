import { screen } from '@testing-library/react'
import { vi, expect, test, afterEach } from 'vitest'
import { renderWithProviders } from '../test/utils'
import Inicio from './Inicio'
afterEach(() => vi.restoreAllMocks())

test('muestra el gasto del mes como hero', async () => {
  vi.stubGlobal('fetch', vi.fn((url: string) => {
    const u = String(url)
    if (u.includes('/api/overview2')) return Promise.resolve(new Response(JSON.stringify({
      patrimonio_ars: 2480500, patrimonio_usd: 2066, blue: 1200,
      kpis: { gasto_mes: 612300, gasto_prev_alt: 500000, ingreso_mes: 980000, deuda_tarjetas: 0, cuotas_futuras: 340000, cuotas_n: 8, disponible: 100000 },
      cashflow: [], hoy: [], por_categoria: [{ cat: 'Comida', total: 210000 }],
    }), { status: 200 }))
    if (u.includes('/api/overview') && !u.includes('/api/overview2')) {
      return Promise.resolve(new Response(JSON.stringify({ accounts: [] }), { status: 200 }))
    }
    if (u.includes('/api/recurring')) {
      return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }))
    }
    return Promise.resolve(new Response('[]', { status: 200 }))
  }))
  renderWithProviders(<Inicio />)
  expect(await screen.findByText('$612.300,00')).toBeInTheDocument()
  expect(screen.getByText('Comida')).toBeInTheDocument()
})

test('deuda en tarjetas suma consumos + cuotas de todas las tarjetas', async () => {
  vi.stubGlobal('fetch', vi.fn((url: string) => {
    const u = String(url)
    if (u.includes('/api/overview2')) return Promise.resolve(new Response(JSON.stringify({
      patrimonio_ars: 1000000, patrimonio_usd: null, blue: 1200,
      kpis: { gasto_mes: 55000, gasto_prev_alt: 45000, ingreso_mes: 200000, deuda_tarjetas: 0, cuotas_futuras: 0, cuotas_n: 0, disponible: 50000 },
      cashflow: [], hoy: [], por_categoria: [],
    }), { status: 200 }))
    if (u.includes('/api/overview') && !u.includes('/api/overview2')) {
      return Promise.resolve(new Response(JSON.stringify({
        accounts: [
          { id: 1, name: 'Visa', type: 'credito', active: 1, balances: [{ currency: 'ARS', balance: -50000 }] },
          { id: 2, name: 'Master', type: 'credito', active: 1, balances: [{ currency: 'ARS', balance: -30000 }] },
        ],
      }), { status: 200 }))
    }
    if (u.includes('/api/recurring')) {
      // Visa: 2 cuotas remaining * $10000 = 20000
      return Promise.resolve(new Response(JSON.stringify([
        { id: 10, description: 'Cuota Visa', amount: 10000, currency: 'ARS', account_id: 1, next_occurrence: '2026-07-01', active: 1, total_installments: 5, installments_fired: 3 },
      ]), { status: 200 }))
    }
    return Promise.resolve(new Response('[]', { status: 200 }))
  }))
  renderWithProviders(<Inicio />)
  // totalDeuda = (50000 + 20000) + (30000 + 0) = 100000
  expect(await screen.findByText('$100.000,00')).toBeInTheDocument()
  // secondary line shows enCuotas
  expect(screen.getByText(/En cuotas:/)).toBeInTheDocument()
})
