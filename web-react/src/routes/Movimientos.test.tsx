import { screen } from '@testing-library/react'
import { vi, expect, test, afterEach } from 'vitest'
import { renderWithProviders } from '../test/utils'
import Movimientos from './Movimientos'

afterEach(() => vi.restoreAllMocks())

test('lista transacciones', async () => {
  vi.stubGlobal('fetch', vi.fn((url: string) => {
    if (String(url).includes('/api/transactions')) return Promise.resolve(new Response(JSON.stringify({
      items: [{ id: 1, type: 'gasto', amount: 5000, currency: 'ARS', description: 'Coca', occurred_at: '2026-06-20', account_id: 1, acc_name: 'MP', cat_name: 'Comida' }],
      total: 1,
    }), { status: 200 }))
    return Promise.resolve(new Response('[]', { status: 200 }))
  }))
  renderWithProviders(<Movimientos />)
  expect(await screen.findByText('Coca')).toBeInTheDocument()
  // el monto aparece en la fila y en el subtotal del día (agrupación por día)
  expect(screen.getAllByText('−$5.000,00').length).toBeGreaterThan(0)
  // encabezado de día y contador de paginación visibles
  expect(screen.getByText('20 de junio')).toBeInTheDocument()
  expect(screen.getByText('Mostrando 1 de 1')).toBeInTheDocument()
})
