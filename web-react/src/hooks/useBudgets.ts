import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiGet, apiPost, apiDelete } from '../lib/api'
import { notifyOk, notifyErr } from '../lib/notify'

export interface Budget {
  id: number
  category_id: number
  amount: number
  name: string
  icon?: string | null
  color?: string | null
  spent: number
}

export function useBudgets() {
  return useQuery({ queryKey: ['budgets'], queryFn: () => apiGet<Budget[]>('/api/budgets') })
}

export function useBudgetMutations() {
  const qc = useQueryClient()
  const inval = () => qc.invalidateQueries({ queryKey: ['budgets'] })
  return {
    upsert: useMutation({
      mutationFn: (b: { category_id: number; amount: number }) => apiPost('/api/budgets', b),
      onSuccess: () => { inval(); notifyOk('Presupuesto guardado') },
      onError: notifyErr,
    }),
    remove: useMutation({
      mutationFn: (id: number) => apiDelete(`/api/budgets/${id}`),
      onSuccess: () => { inval(); notifyOk('Presupuesto eliminado') },
      onError: notifyErr,
    }),
  }
}

// Umbrales de estado (mismos que budget_status de finance.py).
export function budgetPct(b: Budget): number {
  return b.amount > 0 ? (b.spent / b.amount) * 100 : 0
}
export function budgetColor(pct: number): string {
  if (pct >= 100) return 'var(--color-error)'
  if (pct >= 80) return '#e0a800' // ámbar
  return 'var(--color-voltage)'
}
