import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiGet, apiPost, apiPatch, apiDelete } from '../lib/api'
import type { Transaction } from '../lib/types'

export interface TxFilters { period?: string; account_id?: number; category_id?: number; currency?: string; q?: string }

function buildQuery(filters: TxFilters): string {
  const qs = new URLSearchParams()
  const now = new Date()
  const period = filters.period ?? 'mes'
  if (period === 'mes') {
    qs.set('year', String(now.getFullYear())); qs.set('month', String(now.getMonth() + 1))
  } else if (period === 'mes pasado') {
    const d = new Date(now.getFullYear(), now.getMonth() - 1, 1)
    qs.set('year', String(d.getFullYear())); qs.set('month', String(d.getMonth() + 1))
  } else if (period === 'año') {
    qs.set('year', String(now.getFullYear()))
  }
  if (filters.account_id) qs.set('account_id', String(filters.account_id))
  if (filters.category_id) qs.set('category_id', String(filters.category_id))
  if (filters.currency) qs.set('currency', filters.currency)
  if (filters.q) qs.set('q', filters.q)
  return qs.toString()
}

export function useTransactions(filters: TxFilters = {}) {
  const query = buildQuery(filters)
  return useQuery({
    queryKey: ['transactions', filters],
    queryFn: () => apiGet<{ items: Transaction[]; total: number }>(`/api/transactions${query ? `?${query}` : ''}`).then((r) => r.items),
  })
}

export function useTxMutations() {
  const qc = useQueryClient()
  const inval = () => { qc.invalidateQueries({ queryKey: ['transactions'] }); qc.invalidateQueries({ queryKey: ['overview2'] }) }
  return {
    create: useMutation({ mutationFn: (b: Partial<Transaction>) => apiPost('/api/transactions', b), onSuccess: inval }),
    update: useMutation({ mutationFn: ({ id, ...b }: { id: number } & Partial<Transaction>) => apiPatch(`/api/transactions/${id}`, b), onSuccess: inval }),
    remove: useMutation({ mutationFn: (id: number) => apiDelete(`/api/transactions/${id}`), onSuccess: inval }),
    bulkDelete: useMutation({ mutationFn: (ids: number[]) => apiPost('/api/transactions/bulk_delete', { ids }), onSuccess: inval }),
    bulkMove: useMutation({ mutationFn: (b: { ids: number[]; account_id: number }) => apiPost('/api/transactions/bulk_move', b), onSuccess: inval }),
  }
}
