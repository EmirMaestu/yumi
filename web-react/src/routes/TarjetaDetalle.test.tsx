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
