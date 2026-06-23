import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi, expect, test, afterEach } from 'vitest'
import { renderWithProviders } from '../test/utils'
import QuickAddSheet from './QuickAddSheet'

afterEach(() => vi.restoreAllMocks())

test('exige descripción y monto válido', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('[]', { status: 200 })))
  renderWithProviders(<QuickAddSheet open={true} onClose={() => {}} />)
  await userEvent.click(screen.getByRole('button', { name: /guardar/i }))
  expect(await screen.findByText('Falta descripción')).toBeInTheDocument()
})
