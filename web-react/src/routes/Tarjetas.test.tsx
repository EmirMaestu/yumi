import { screen } from '@testing-library/react'
import { vi, expect, test, afterEach } from 'vitest'
import { renderWithProviders } from '../test/utils'
import Tarjetas from './Tarjetas'

afterEach(() => vi.restoreAllMocks())

test('muestra una tarjeta con A pagar del ciclo cerrado', async () => {
  vi.stubGlobal('fetch', vi.fn((url: string) => {
    const u = String(url)
    if (u.includes('/api/accounts')) return Promise.resolve(new Response(JSON.stringify([{ id: 1, name: 'Visa Galicia', type: 'credito', active: 1 }]), { status: 200 }))
    if (u.includes('/api/vencimientos')) return Promise.resolve(new Response(JSON.stringify([{ account_id: 1, account_name: 'Visa Galicia', next_due: '2026-07-10', next_closing: '2026-07-03', ciclo_cerrado: [{ currency: 'ARS', total: 500000 }], ciclo_abierto: [] }]), { status: 200 }))
    return Promise.resolve(new Response('[]', { status: 200 }))
  }))
  renderWithProviders(<Tarjetas />)
  expect(await screen.findByText('Visa Galicia')).toBeInTheDocument()
  expect(screen.getByText('$500.000,00')).toBeInTheDocument() // ciclo_cerrado total
})
