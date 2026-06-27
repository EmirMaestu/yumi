import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiGet, apiPatch } from '../lib/api'
import { type AdminOverview, type AdminUsersResponse, type AdminReferralsResponse, type AdminHouseholdsResponse } from '../lib/types'

export function useAdminOverview() {
  return useQuery({
    queryKey: ['admin', 'overview'],
    queryFn: () => apiGet<AdminOverview>('/api/admin/overview'),
  })
}

export function useAdminUsers() {
  return useQuery({
    queryKey: ['admin', 'users'],
    queryFn: () => apiGet<AdminUsersResponse>('/api/admin/users'),
  })
}

export function useAdminReferrals() {
  return useQuery({
    queryKey: ['admin', 'referrals'],
    queryFn: () => apiGet<AdminReferralsResponse>('/api/admin/referrals'),
  })
}

export function useAdminHouseholds() {
  return useQuery({
    queryKey: ['admin', 'households'],
    queryFn: () => apiGet<AdminHouseholdsResponse>('/api/admin/households'),
  })
}

interface UserPatch {
  id: number
  plan?: string
  active?: boolean
  name?: string
}

export function useAdminUserMutations() {
  const qc = useQueryClient()
  const inval = () => {
    qc.invalidateQueries({ queryKey: ['admin'] })
    qc.invalidateQueries({ queryKey: ['me'] })
  }
  return {
    update: useMutation({
      mutationFn: ({ id, ...b }: UserPatch) => apiPatch<{ ok: boolean }>(`/api/admin/users/${id}`, b),
      onSuccess: inval,
    }),
  }
}
