import { screen } from '@testing-library/react'
import { vi, expect, test, afterEach } from 'vitest'
import { renderWithProviders } from '../test/utils'
import Hoy from './Hoy'

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

function makeFetch(overview = baseOverview, tareas: unknown[] = []) {
  return vi.fn((url: string) => {
    const u = String(url)
    if (u.includes('/api/overview2')) {
      return Promise.resolve(new Response(JSON.stringify(overview), { status: 200 }))
    }
    if (u.includes('/api/tareas')) {
      return Promise.resolve(new Response(JSON.stringify(tareas), { status: 200 }))
    }
    if (u.includes('/api/vencimientos')) {
      // "A pagar" = ciclo cerrado (lo que vence), no el saldo total
      return Promise.resolve(new Response(JSON.stringify([
        { account_id: 1, account_name: 'Visa', next_due: '2026-07-10', next_closing: '2026-07-03', ciclo_cerrado: [{ currency: 'ARS', total: 12000 }], ciclo_abierto: [] },
      ]), { status: 200 }))
    }
    return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }))
  })
}

test('renderiza los ítems de hoy del overview', async () => {
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

test('muestra tareas pendientes', async () => {
  const tareas = [
    { id: 1, text: 'Comprar leche', priority: 'alta', status: 'pendiente', user_id: 1, created_at: '2026-06-24T00:00:00', due_at: null, completed_at: null },
    { id: 2, text: 'Llamar al médico', priority: 'media', status: 'pendiente', user_id: 1, created_at: '2026-06-24T00:00:00', due_at: null, completed_at: null },
  ]
  vi.stubGlobal('fetch', makeFetch(baseOverview, tareas))
  renderWithProviders(<Hoy />)

  expect(await screen.findByText('Comprar leche')).toBeInTheDocument()
  expect(screen.getByText('Llamar al médico')).toBeInTheDocument()
  expect(screen.getByText('alta')).toBeInTheDocument()
})

test('muestra kpis financieros en la mini-card', async () => {
  vi.stubGlobal('fetch', makeFetch())
  renderWithProviders(<Hoy />)

  expect(await screen.findByText('$50.000,00')).toBeInTheDocument() // gastado
  expect(screen.getByText('$12.000,00')).toBeInTheDocument()        // a pagar = ciclo cerrado
  expect(screen.getByText('$80.000,00')).toBeInTheDocument()        // disponible
})
