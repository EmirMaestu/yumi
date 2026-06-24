import { screen } from '@testing-library/react'
import { vi, expect, test, afterEach } from 'vitest'
import { Routes, Route } from 'react-router-dom'
import { renderWithProviders } from '../test/utils'
import TarjetaDetalle from './TarjetaDetalle'

afterEach(() => vi.restoreAllMocks())

test('muestra movimientos de la tarjeta para el mes actual', async () => {
  vi.stubGlobal('fetch', vi.fn((url: string) => {
    const u = String(url)
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
        ciclo_cerrado: [{ currency: 'ARS', total: 50000 }],
        ciclo_abierto: [{ currency: 'ARS', total: 20000 }],
      }]), { status: 200 }))
    }
    if (u.includes('/api/recurring')) {
      return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }))
    }
    if (u.includes('/api/transactions')) {
      return Promise.resolve(new Response(JSON.stringify({
        items: [
          { id: 10, type: 'gasto', amount: 5000, currency: 'ARS', description: 'Hamburguesas', occurred_at: '2026-06-15', account_id: 1, cat_name: 'Comida' },
          { id: 11, type: 'gasto', amount: 1200, currency: 'ARS', description: 'Compra de gaseosas', occurred_at: '2026-06-18', account_id: 1, cat_name: null },
        ],
        total: 2,
      }), { status: 200 }))
    }
    return Promise.resolve(new Response('[]', { status: 200 }))
  }))

  renderWithProviders(
    <Routes>
      <Route path="/tarjetas/:id" element={<TarjetaDetalle />} />
    </Routes>,
    '/tarjetas/1',
  )

  expect(await screen.findByText('Movimientos de la tarjeta')).toBeInTheDocument()
  expect(await screen.findByText('Hamburguesas')).toBeInTheDocument()
  expect(screen.getByText('Compra de gaseosas')).toBeInTheDocument()
  expect(screen.getByText('−$5.000,00')).toBeInTheDocument()
  expect(screen.getByText('−$1.200,00')).toBeInTheDocument()
})

test('hero deuda total incluye consumos + cuotas pendientes', async () => {
  vi.stubGlobal('fetch', vi.fn((url: string) => {
    const u = String(url)
    if (u.includes('/api/overview') && !u.includes('/api/overview2')) {
      return Promise.resolve(new Response(JSON.stringify({
        accounts: [{ id: 1, name: 'Visa Galicia', type: 'credito', active: 1, balances: [{ currency: 'ARS', balance: -100000 }] }],
      }), { status: 200 }))
    }
    if (u.includes('/api/vencimientos')) {
      return Promise.resolve(new Response(JSON.stringify([{
        account_id: 1,
        account_name: 'Visa Galicia',
        next_due: '2026-07-10',
        next_closing: '2026-07-03',
        ciclo_cerrado: [],
        ciclo_abierto: [],
      }]), { status: 200 }))
    }
    if (u.includes('/api/recurring')) {
      // 3 cuotas remaining * $20000 = 60000
      return Promise.resolve(new Response(JSON.stringify([
        { id: 5, description: 'Laptop', amount: 20000, currency: 'ARS', account_id: 1, next_occurrence: '2026-07-01', active: 1, total_installments: 6, installments_fired: 3 },
      ]), { status: 200 }))
    }
    if (u.includes('/api/transactions')) {
      return Promise.resolve(new Response(JSON.stringify({ items: [], total: 0 }), { status: 200 }))
    }
    return Promise.resolve(new Response('[]', { status: 200 }))
  }))

  renderWithProviders(
    <Routes>
      <Route path="/tarjetas/:id" element={<TarjetaDetalle />} />
    </Routes>,
    '/tarjetas/1',
  )

  // deudaTotal = abs(-100000) + (6-3)*20000 = 100000 + 60000 = 160000
  expect(await screen.findByText('$160.000,00')).toBeInTheDocument()
  expect(screen.getByText('Deuda total')).toBeInTheDocument()
  // A pagar este mes = ciclo en curso (abierto 0 + 1 cuota 20000)
  expect(screen.getByText(/A pagar este mes \(cierra/)).toBeInTheDocument()
  expect(screen.getByText('$20.000,00')).toBeInTheDocument()
  // Cuota actual = pagadas + 1 → 3 pagadas, vas por la 4 de 6 (sin "pagadas 3/6")
  expect(screen.getByText(/Cuota 4 de 6/)).toBeInTheDocument()
  expect(screen.getByText(/Te falta:/)).toBeInTheDocument()
  expect(screen.getByText(/3 cuotas/)).toBeInTheDocument()
})

test('muestra estado vacío cuando no hay movimientos', async () => {
  vi.stubGlobal('fetch', vi.fn((url: string) => {
    const u = String(url)
    if (u.includes('/api/overview') && !u.includes('/api/overview2')) {
      return Promise.resolve(new Response(JSON.stringify({
        accounts: [{ id: 1, name: 'Visa Galicia', type: 'credito', active: 1, balances: [{ currency: 'ARS', balance: 0 }] }],
      }), { status: 200 }))
    }
    if (u.includes('/api/vencimientos')) {
      return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }))
    }
    if (u.includes('/api/recurring')) {
      return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }))
    }
    if (u.includes('/api/transactions')) {
      return Promise.resolve(new Response(JSON.stringify({ items: [], total: 0 }), { status: 200 }))
    }
    return Promise.resolve(new Response('[]', { status: 200 }))
  }))

  renderWithProviders(
    <Routes>
      <Route path="/tarjetas/:id" element={<TarjetaDetalle />} />
    </Routes>,
    '/tarjetas/1',
  )

  expect(await screen.findByText('Sin movimientos este mes en esta tarjeta.')).toBeInTheDocument()
})
