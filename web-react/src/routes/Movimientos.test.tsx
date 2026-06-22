import { screen } from '@testing-library/react'
import { vi, expect, test, afterEach } from 'vitest'
import { renderWithProviders } from '../test/utils'
import Movimientos from './Movimientos'

afterEach(() => vi.restoreAllMocks())

test('lista transacciones', async () => {
  vi.stubGlobal('fetch', vi.fn((url: string) => {
    if (String(url).includes('/api/transactions')) return Promise.resolve(new Response(JSON.stringify([
      { id: 1, type: 'gasto', amount: 5000, currency: 'ARS', description: 'Coca', occurred_at: '2026-06-20', account_id: 1, account_name: 'MP', category_name: 'Comida' },
    ]), { status: 200 }))
    return Promise.resolve(new Response('[]', { status: 200 }))
  }))
  renderWithProviders(<Movimientos />)
  expect(await screen.findByText('Coca')).toBeInTheDocument()
  expect(screen.getByText('−$5.000')).toBeInTheDocument()
})
