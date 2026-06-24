import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiGet, apiPost, apiPatch } from '../lib/api'
import { type HabitosResponse } from '../lib/types'

export function useHabitos(days = 7) {
  return useQuery({
    queryKey: ['habitos', days],
    queryFn: () => apiGet<HabitosResponse>(`/api/habitos?days=${days}`),
  })
}

interface HabitoCreate {
  name: string
  value?: number | null
  unit?: string | null
  note?: string | null
  logged_at?: string | null
}

interface HabitoUpdate {
  id: number
  name?: string
  value?: number | null
  unit?: string | null
  note?: string | null
  logged_at?: string | null
}

export function useHabitosMutations() {
  const qc = useQueryClient()
  const inval = () => qc.invalidateQueries({ queryKey: ['habitos'] })

  return {
    create: useMutation({
      mutationFn: (b: HabitoCreate) => apiPost<{ id: number; ok: boolean }>('/api/habitos', b),
      onSuccess: inval,
    }),
    update: useMutation({
      mutationFn: ({ id, ...b }: HabitoUpdate) => apiPatch<{ ok: boolean }>(`/api/habitos/${id}`, b),
      onSuccess: inval,
    }),
    // soft-delete a single habit-log entry (papelera)
    remove: useMutation({
      mutationFn: (id: number) => apiPost<{ ok: boolean }>(`/api/trash/habitos/${id}`),
      onSuccess: inval,
    }),
  }
}
