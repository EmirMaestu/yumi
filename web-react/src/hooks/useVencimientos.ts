import { useQuery } from '@tanstack/react-query'
import { apiGet } from '../lib/api'
import { type VencimientoCard } from '../lib/types'
export function useVencimientos() {
  return useQuery({ queryKey: ['vencimientos'], queryFn: () => apiGet<VencimientoCard[]>('/api/vencimientos') })
}
