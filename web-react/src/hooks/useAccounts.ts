import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiGet, apiPost, apiPatch, apiDelete } from '../lib/api'
import { type Account } from '../lib/types'
export function useAccounts() {
  return useQuery({ queryKey: ['accounts'], queryFn: () => apiGet<Account[]>('/api/accounts') })
}
export function useAccountMutations() {
  const qc = useQueryClient()
  const inval = () => qc.invalidateQueries({ queryKey: ['accounts'] })
  return {
    create: useMutation({ mutationFn: (b: Partial<Account>) => apiPost('/api/accounts', b), onSuccess: inval }),
    update: useMutation({ mutationFn: ({ id, ...b }: { id: number } & Partial<Account>) => apiPatch(`/api/accounts/${id}`, b), onSuccess: inval }),
    remove: useMutation({ mutationFn: (id: number) => apiDelete(`/api/accounts/${id}`), onSuccess: inval }),
  }
}
export function useAccountsWithBalances() {
  return useQuery({
    queryKey: ['accounts-balances'],
    queryFn: async () => {
      const o = await apiGet<{ accounts: Account[] }>('/api/overview')
      return o.accounts
    },
  })
}
