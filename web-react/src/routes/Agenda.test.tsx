import { screen } from '@testing-library/react'
import { vi, expect, test, afterEach } from 'vitest'
import { renderWithProviders } from '../test/utils'
import Agenda from './Agenda'

afterEach(() => vi.restoreAllMocks())

const tomorrow = new Date()
tomorrow.setDate(tomorrow.getDate() + 1)
tomorrow.setHours(10, 0, 0, 0)
const tomorrowIso = tomorrow.toISOString().slice(0, 16)

const mockEventos = [
  {
    id: 1,
    title: 'Reunión de equipo',
    starts_at: tomorrowIso,
    location: 'Oficina',
    notes: null,
    user_id: 1,
  },
]

const mockRecordatorios = [
  {
    id: 2,
    text: 'Llamar al banco',
    remind_at: tomorrowIso,
    fired: 0,
    source: 'web',
    user_id: 1,
  },
]

function makeFetch(eventos = mockEventos, recordatorios = mockRecordatorios) {
  return vi.fn((url: string) => {
    const u = String(url)
    if (u.includes('/api/eventos')) {
      // past=true returns empty, past=false returns eventos
      if (u.includes('past=true')) {
        return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }))
      }
      return Promise.resolve(new Response(JSON.stringify(eventos), { status: 200 }))
    }
    if (u.includes('/api/recordatorios')) {
      return Promise.resolve(new Response(JSON.stringify(recordatorios), { status: 200 }))
    }
    return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }))
  })
}

test('muestra un evento y un recordatorio agrupados por día', async () => {
  vi.stubGlobal('fetch', makeFetch())

  renderWithProviders(<Agenda />)

  expect(await screen.findByText('Reunión de equipo')).toBeInTheDocument()
  expect(screen.getByText('Llamar al banco')).toBeInTheDocument()
  // recordatorio muestra su subtítulo
  expect(screen.getByText(/Recordatorio ·/)).toBeInTheDocument()
  // day group label
  expect(screen.getAllByText('Mañana').length).toBeGreaterThan(0)
})

test('muestra EmptyState si no hay ítems', async () => {
  vi.stubGlobal('fetch', makeFetch([], []))

  renderWithProviders(<Agenda />)

  expect(await screen.findByText(/Sin eventos ni recordatorios/)).toBeInTheDocument()
})
