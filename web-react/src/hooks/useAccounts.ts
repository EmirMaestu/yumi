import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiGet, apiPost, apiPatch, apiDelete } from '../lib/api'
import { notifyOk, notifyErr } from '../lib/notify'
import { type Account } from '../lib/types'
export function useAccounts() {
  return useQuery({ queryKey: ['accounts'], queryFn: () => apiGet<Account[]>('/api/accounts') })
}
export function useAccountMutations() {
  const qc = useQueryClient()
  const inval = () => Promise.all([
    qc.invalidateQueries({ queryKey: ['accounts'] }),
    qc.invalidateQueries({ queryKey: ['accounts-balances'] }),
    qc.invalidateQueries({ queryKey: ['overview2'] }),
    qc.invalidateQueries({ queryKey: ['vencimientos'] }),
  ])
  return {
    create: useMutation({ mutationFn: (b: Partial<Account>) => apiPost('/api/accounts', b), onSuccess: () => { inval(); notifyOk('Cuenta creada') }, onError: notifyErr }),
    update: useMutation({ mutationFn: ({ id, ...b }: { id: number } & Partial<Account>) => apiPatch(`/api/accounts/${id}`, b), onSuccess: () => { inval(); notifyOk('Cuenta actualizada') }, onError: notifyErr }),
    remove: useMutation({ mutationFn: (id: number) => apiDelete(`/api/accounts/${id}`), onSuccess: () => { inval(); notifyOk('Cuenta eliminada') }, onError: notifyErr }),
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
