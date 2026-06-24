import { screen } from '@testing-library/react'
import { vi, expect, test, afterEach } from 'vitest'
import { renderWithProviders } from '../test/utils'
import Cuentas from './Cuentas'
afterEach(() => vi.restoreAllMocks())
test('lista cuentas con saldo', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({
    accounts: [{ id: 1, name: 'MP', type: 'billetera', active: 1, balances: [{ currency: 'ARS', balance: 250000 }] }],
  }), { status: 200 })))
  renderWithProviders(<Cuentas />)
  expect(await screen.findByText('MP')).toBeInTheDocument()
  expect(screen.getByText('$250.000,00')).toBeInTheDocument()
})
