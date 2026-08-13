import { screen } from '@testing-library/react'
import { vi, expect, test, afterEach } from 'vitest'
import { renderWithProviders } from '../test/utils'
import Hoy from './Hoy'

// El Inicio (diseño 1a) lee LayoutCtx vía useOutletContext; en el test no hay
// <Outlet>, así que lo stubbeamos manteniendo el resto de react-router-dom real.
vi.mock('react-router-dom', async (orig) => {
  const actual = await orig<typeof import('react-router-dom')>()
  return { ...actual, useOutletContext: () => ({ openAdd: vi.fn(), openExpense: vi.fn() }) }
})

afterEach(() => vi.restoreAllMocks())

const baseOverview = {
  patrimonio_ars: 1000000,
  patrimonio_usd: null,
  blue: 1200,
  kpis: {
    gasto_mes: 50000,
    gasto_prev_alt: 45000,
    ingreso_mes: 200000,
    deuda_tarjetas: 12000,
    cuotas_futuras: 30000,
    cuotas_n: 3,
    disponible: 80000,
  },
  cashflow: [],
  hoy: [
    { tipo: 'evento', titulo: 'Reunión con cliente', sub: 'Oficina', hora: '10:00' },
    { tipo: 'recordatorio', titulo: 'Pagar factura', sub: '', hora: '18:00' },
  ],
  por_categoria: [],
}

function makeFetch(overview = baseOverview) {
  return vi.fn((url: string) => {
    const u = String(url)
    if (u.includes('/api/overview2')) {
      return Promise.resolve(new Response(JSON.stringify(overview), { status: 200 }))
    }
    if (u.includes('/api/vencimientos')) {
      // "A pagar" = ciclo en curso (compras del ciclo + cuotas del mes)
      return Promise.resolve(new Response(JSON.stringify([
        { account_id: 1, account_name: 'Visa', next_due: '2026-07-10', next_closing: '2026-07-03', ciclo_cerrado: [], ciclo_abierto: [{ currency: 'ARS', total: 12000 }] },
      ]), { status: 200 }))
    }
    return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }))
  })
}

test('renderiza los ítems de hoy del overview en "Tu día"', async () => {
  vi.stubGlobal('fetch', makeFetch())
  renderWithProviders(<Hoy />)

  expect(await screen.findByText('Reunión con cliente')).toBeInTheDocument()
  expect(screen.getByText('Pagar factura')).toBeInTheDocument()
  expect(screen.getByText('10:00')).toBeInTheDocument()
  expect(screen.getByText('18:00')).toBeInTheDocument()
  expect(screen.getByText('Oficina')).toBeInTheDocument()
})

test('muestra EmptyState cuando hoy está vacío', async () => {
  vi.stubGlobal('fetch', makeFetch({ ...baseOverview, hoy: [] }))
  renderWithProviders(<Hoy />)

  expect(await screen.findByText(/Nada agendado para hoy/)).toBeInTheDocument()
})

test('muestra el disponible y la línea de gastado / a pagar', async () => {
  vi.stubGlobal('fetch', makeFetch())
  renderWithProviders(<Hoy />)

  // Disponible (héroe, componente Money → texto aislado)
  expect(await screen.findByText('$80.000,00')).toBeInTheDocument()
  // Subtítulo combinado: "Gastado $50.000,00 · A pagar $12.000,00 este mes"
  expect(screen.getByText(/Gastado.*50\.000.*A pagar.*12\.000/)).toBeInTheDocument()
})
