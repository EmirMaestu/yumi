import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiGet, apiPost, apiPatch, apiDelete } from '../lib/api'
import { type Transaction } from '../lib/types'

export interface TxFilters { period?: string; account_id?: number; category_id?: number; currency?: string; q?: string }

export function useTransactions(filters: TxFilters = {}) {
  const qs = new URLSearchParams()
  Object.entries(filters).forEach(([k, v]) => { if (v !== undefined && v !== '') qs.set(k, String(v)) })
  const query = qs.toString()
  return useQuery({
    queryKey: ['transactions', filters],
    queryFn: () => apiGet<Transaction[]>(`/api/transactions${query ? `?${query}` : ''}`),
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
