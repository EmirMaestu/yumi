import { useQuery } from '@tanstack/react-query'
import { apiGet } from '../lib/api'

export interface SplitsSummary {
  status: 'even' | 'they_owe' | 'you_owe'
  amount: number
  other_name: string
}

// 404 en hogar de 1 persona → no se muestra la card. No reintenta.
export function useSplitsSummary() {
  return useQuery({
    queryKey: ['splits-summary'],
    queryFn: () => apiGet<SplitsSummary>('/api/splits/summary'),
    retry: false,
  })
}
