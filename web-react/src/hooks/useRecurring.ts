import { useQuery } from '@tanstack/react-query'
import { apiGet } from '../lib/api'
import { type Recurring } from '../lib/types'
export function useRecurring() {
  return useQuery({ queryKey: ['recurring'], queryFn: () => apiGet<Recurring[]>('/api/recurring') })
}
