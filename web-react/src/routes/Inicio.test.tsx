import { screen } from '@testing-library/react'
import { vi, expect, test, afterEach } from 'vitest'
import { renderWithProviders } from '../test/utils'
import Inicio from './Inicio'
afterEach(() => vi.restoreAllMocks())
test('muestra el gasto del mes como hero', async () => {
  vi.stubGlobal('fetch', vi.fn((url: string) => {
    if (String(url).includes('/api/overview2')) return Promise.resolve(new Response(JSON.stringify({
      patrimonio_ars: 2480500, patrimonio_usd: 2066, blue: 1200,
      kpis: { gasto_mes: 612300, gasto_prev_alt: 500000, ingreso_mes: 980000, deuda_tarjetas: 0, cuotas_futuras: 340000, cuotas_n: 8, disponible: 100000 },
      cashflow: [], hoy: [], por_categoria: [{ cat: 'Comida', total: 210000 }],
    }), { status: 200 }))
    return Promise.resolve(new Response('[]', { status: 200 }))
  }))
  renderWithProviders(<Inicio />)
  expect(await screen.findByText('$612.300,00')).toBeInTheDocument()
  expect(screen.getByText('Comida')).toBeInTheDocument()
})
