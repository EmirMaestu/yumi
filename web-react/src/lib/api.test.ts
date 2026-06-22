import { afterEach, expect, test, vi } from 'vitest'
import { apiGet, apiPost, setUnauthorizedHandler, ApiError } from './api'

afterEach(() => vi.restoreAllMocks())

test('apiGet manda credentials include y parsea JSON', async () => {
  const fetchMock = vi.fn().mockResolvedValue(
    new Response(JSON.stringify({ ok: true }), { status: 200, headers: { 'Content-Type': 'application/json' } }),
  )
  vi.stubGlobal('fetch', fetchMock)

  const data = await apiGet<{ ok: boolean }>('/api/me')

  expect(data.ok).toBe(true)
  const [, opts] = fetchMock.mock.calls[0]
  expect(opts.credentials).toBe('include')
})

test('apiPost envía body JSON', async () => {
  const fetchMock = vi.fn().mockResolvedValue(new Response('{}', { status: 200 }))
  vi.stubGlobal('fetch', fetchMock)

  await apiPost('/api/transactions', { amount: 100 })

  const [, opts] = fetchMock.mock.calls[0]
  expect(opts.method).toBe('POST')
  expect(JSON.parse(opts.body)).toEqual({ amount: 100 })
})

test('un 401 dispara el handler y lanza ApiError', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('no', { status: 401 })))
  const handler = vi.fn()
  setUnauthorizedHandler(handler)

  await expect(apiGet('/api/me')).rejects.toBeInstanceOf(ApiError)
  expect(handler).toHaveBeenCalledOnce()
})

test('un 204 devuelve undefined sin parsear body', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(null, { status: 204 })))
  await expect(apiGet('/api/transactions/1')).resolves.toBeUndefined()
})
