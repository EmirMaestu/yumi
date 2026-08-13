import { useQuery } from '@tanstack/react-query'
import { apiGet } from '../lib/api'
import type { HouseholdInfo } from '../lib/types'

// Estado del hogar + links para invitar a la pareja/familia (misma lógica que /invitar del bot).
export function useHousehold() {
  return useQuery({
    queryKey: ['household'],
    queryFn: () => apiGet<HouseholdInfo>('/api/household'),
    staleTime: 60 * 1000,
  })
}
