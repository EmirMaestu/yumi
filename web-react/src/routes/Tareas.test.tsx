import { screen, fireEvent } from '@testing-library/react'
import { vi, expect, test, afterEach } from 'vitest'
import { renderWithProviders } from '../test/utils'
import Tareas from './Tareas'

afterEach(() => vi.restoreAllMocks())

const mockTareas = [
  {
    id: 1,
    text: 'Comprar leche',
    priority: 'alta',
    due_at: null,
    user_id: 1,
    created_at: '2026-06-20T10:00:00',
    status: 'pendiente',
    completed_at: null,
    shared: 0,
  },
  {
    id: 2,
    text: 'Llamar al médico',
    priority: 'media',
    due_at: '2026-06-30',
    user_id: 1,
    created_at: '2026-06-19T10:00:00',
    status: 'hecha',
    completed_at: '2026-06-21T09:00:00',
    shared: 0,
  },
]

test('lista tareas pendientes y hechas', async () => {
  vi.stubGlobal('fetch', vi.fn((url: string) => {
    if (String(url).includes('/api/tareas')) {
      return Promise.resolve(new Response(JSON.stringify(mockTareas), { status: 200 }))
    }
    return Promise.resolve(new Response('[]', { status: 200 }))
  }))

  renderWithProviders(<Tareas />)

  // Por defecto (filtro "Todas") se ven las pendientes
  expect(await screen.findByText('Comprar leche')).toBeInTheDocument()
  // Las hechas viven detrás del filtro "Hechas"
  fireEvent.click(screen.getByText('Hechas'))
  expect(await screen.findByText('Llamar al médico')).toBeInTheDocument()
  expect(screen.getByText('Completadas')).toBeInTheDocument()
})

test('muestra EmptyState si no hay tareas', async () => {
  vi.stubGlobal('fetch', vi.fn((url: string) => {
    if (String(url).includes('/api/tareas')) {
      return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }))
    }
    return Promise.resolve(new Response('[]', { status: 200 }))
  }))

  renderWithProviders(<Tareas />)
  expect(await screen.findByText(/Sin tareas/)).toBeInTheDocument()
})
