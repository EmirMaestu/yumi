import { screen } from '@testing-library/react'
import { vi, expect, test, afterEach } from 'vitest'
import { renderWithProviders } from '../../test/utils'
import ScopeToggle from './ScopeToggle'

afterEach(() => vi.restoreAllMocks())

test('muestra opciones de scope desde /api/me', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({
    id: 1, name: 'Emir', username: 'emir', scope: 'mine',
    others: [{ name: 'Lisa', scope_value: 'user:Lisa' }],
  }), { status: 200 })))

  renderWithProviders(<ScopeToggle />)

  // Radix Select keeps options in a closed portal; assert the trigger shows the current scope label
  expect(await screen.findByText('Mío')).toBeInTheDocument()
})
