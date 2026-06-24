import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiGet, apiPost, apiPatch, apiDelete } from '../lib/api'
import { type Nota } from '../lib/types'

// The backend stores `tags` as a JSON string (e.g. '["claves"]'), so it can come
// back as a string, null, or (defensively) an array. Always normalize to string[].
function parseTags(raw: unknown): string[] {
  if (Array.isArray(raw)) return raw.filter((t): t is string => typeof t === 'string')
  if (typeof raw === 'string' && raw.trim()) {
    try {
      const parsed = JSON.parse(raw)
      if (Array.isArray(parsed)) return parsed.filter((t): t is string => typeof t === 'string')
    } catch {
      return raw.split(',').map((s) => s.trim()).filter(Boolean)
    }
  }
  return []
}

export function useNotas(q?: string) {
  const qs = q ? `?q=${encodeURIComponent(q)}` : ''
  return useQuery({
    queryKey: ['notas', q ?? ''],
    queryFn: async () => {
      const rows = await apiGet<(Omit<Nota, 'tags'> & { tags: unknown })[]>(`/api/notas${qs}`)
      return rows.map((r): Nota => ({ ...r, tags: parseTags(r.tags) }))
    },
  })
}

interface NotaCreate {
  text: string
  tags?: string[]
}

interface NotaUpdate {
  id: number
  text?: string
  tags?: string[]
}

export function useNotasMutations() {
  const qc = useQueryClient()
  const inval = () => qc.invalidateQueries({ queryKey: ['notas'] })

  return {
    create: useMutation({
      mutationFn: (b: NotaCreate) => apiPost<{ id: number; ok: boolean }>('/api/notas', b),
      onSuccess: inval,
    }),
    update: useMutation({
      mutationFn: ({ id, ...b }: NotaUpdate) => apiPatch<{ ok: boolean }>(`/api/notas/${id}`, b),
      onSuccess: inval,
    }),
    remove: useMutation({
      mutationFn: (id: number) => apiDelete<{ ok: boolean }>(`/api/notas/${id}`),
      onSuccess: inval,
    }),
  }
}
