import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiGet, apiPost, apiPatch, apiDelete } from '../lib/api'
import { type Recordatorio } from '../lib/types'

export function useRecordatorios(includeFired = false) {
  return useQuery({
    queryKey: ['recordatorios', includeFired],
    queryFn: () =>
      apiGet<Recordatorio[]>(`/api/recordatorios?include_fired=${includeFired}`),
  })
}

interface RecordatorioCreate {
  text: string
  remind_at: string
  event_id?: number | null  // vincular a un evento (opcional)
}

interface RecordatorioUpdate {
  id: number
  text?: string
  remind_at?: string
  event_id?: number | null  // null = desvincular
}

export type SnoozePreset = '1h' | 'manana' | 'semana'

export function useRecordatoriosMutations() {
  const qc = useQueryClient()
  // los recordatorios se muestran embebidos en los eventos (event.reminders) →
  // al crear/borrar/editar uno hay que refrescar también ['eventos'] para verlo en tiempo real
  const inval = () => {
    qc.invalidateQueries({ queryKey: ['recordatorios'] })
    qc.invalidateQueries({ queryKey: ['eventos'] })
  }

  return {
    create: useMutation({
      mutationFn: (b: RecordatorioCreate) =>
        apiPost<{ id: number; ok: boolean }>('/api/recordatorios', b),
      onSuccess: inval,
    }),
    update: useMutation({
      mutationFn: ({ id, ...b }: RecordatorioUpdate) =>
        apiPatch<{ ok: boolean }>(`/api/recordatorios/${id}`, b),
      onSuccess: inval,
    }),
    snooze: useMutation({
      mutationFn: ({ id, preset }: { id: number; preset: SnoozePreset }) =>
        apiPost<{ ok: boolean; remind_at: string }>(
          `/api/recordatorios/${id}/snooze?preset=${preset}`,
        ),
      onSuccess: inval,
    }),
    remove: useMutation({
      mutationFn: (id: number) => apiDelete<{ ok: boolean }>(`/api/recordatorios/${id}`),
      onSuccess: inval,
    }),
  }
}
