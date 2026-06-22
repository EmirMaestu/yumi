import { useQuery } from '@tanstack/react-query'
import { apiGet } from '../lib/api'
import { type Overview2 } from '../lib/types'
export function useOverview() {
  return useQuery({ queryKey: ['overview2'], queryFn: () => apiGet<Overview2>('/api/overview2') })
}
