import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiGet, apiPost, apiPatch, apiDelete } from '../lib/api'
import { notifyOk, notifyErr } from '../lib/notify'
import { type Recurring } from '../lib/types'

export function useRecurring(includeInactive = false) {
  return useQuery({
    queryKey: ['recurring', includeInactive],
    queryFn: () => apiGet<Recurring[]>(`/api/recurring${includeInactive ? '?include_inactive=true' : ''}`),
  })
}

interface RecurringCreate {
  description: string
  amount: number
  account_id: number
  day_of_month: number
  total_installments?: number | null
  installments_fired?: number | null
  currency?: string
  category_id?: number | null
}

interface RecurringUpdate {
  id: number
  description?: string
  amount?: number
  total_installments?: number | null
  installments_fired?: number | null
  active?: number
  day_of_month?: number
}

export function useRecurringMutations() {
  const qc = useQueryClient()
  const inval = () =>
    Promise.all([
      qc.invalidateQueries({ queryKey: ['recurring'] }),
      qc.invalidateQueries({ queryKey: ['vencimientos'] }),
      qc.invalidateQueries({ queryKey: ['overview2'] }),
    ])

  return {
    create: useMutation({
      mutationFn: (b: RecurringCreate) => apiPost('/api/recurring', b),
      onSuccess: () => { inval(); notifyOk('Recurrente creado') },
      onError: notifyErr,
    }),
    update: useMutation({
      mutationFn: ({ id, ...b }: RecurringUpdate) => apiPatch(`/api/recurring/${id}`, b),
      onSuccess: (_d, vars) => {
        inval()
        // El mismo update sirve para editar y para pausar/reactivar (toggle de active).
        if (vars.active !== undefined && Object.keys(vars).length === 2) {
          notifyOk(vars.active ? 'Recurrente reactivado' : 'Recurrente pausado')
        } else {
          notifyOk('Recurrente actualizado')
        }
      },
      onError: notifyErr,
    }),
    remove: useMutation({
      mutationFn: (id: number) => apiDelete(`/api/recurring/${id}`),
      onSuccess: () => { inval(); notifyOk('Recurrente eliminado') },
      onError: notifyErr,
    }),
  }
}
