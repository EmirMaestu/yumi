import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiGet, apiPost, apiPatch, apiDelete } from '../lib/api'
import { notifyOk, notifyErr } from '../lib/notify'

export interface SavingsGoal {
  id: number
  name: string
  target_amount: number
  currency: string
  current_amount: number
  deadline?: string | null
  active: number
}

export function useSavingsGoals() {
  return useQuery({ queryKey: ['savings_goals'], queryFn: () => apiGet<SavingsGoal[]>('/api/savings_goals') })
}

export function useSavingsGoalMutations() {
  const qc = useQueryClient()
  const inval = () => qc.invalidateQueries({ queryKey: ['savings_goals'] })
  return {
    create: useMutation({
      mutationFn: (b: { name: string; target_amount: number; currency: string; deadline?: string | null }) => apiPost('/api/savings_goals', b),
      onSuccess: () => { inval(); notifyOk('Meta creada') }, onError: notifyErr,
    }),
    update: useMutation({
      mutationFn: ({ id, ...b }: { id: number } & Partial<SavingsGoal>) => apiPatch(`/api/savings_goals/${id}`, b),
      onSuccess: () => { inval(); notifyOk('Meta actualizada') }, onError: notifyErr,
    }),
    remove: useMutation({
      mutationFn: (id: number) => apiDelete(`/api/savings_goals/${id}`),
      onSuccess: () => { inval(); notifyOk('Meta eliminada') }, onError: notifyErr,
    }),
  }
}
