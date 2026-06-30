import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiGet, apiPost } from '../lib/api'
import type { HouseholdMember, ShareEntity, ShareState } from '../lib/types'

// Mapea la entidad de compartir a la queryKey de su listado, para invalidar tras compartir.
const LIST_KEY: Record<ShareEntity, string> = { tareas: 'tareas', notas: 'notas', lists: 'listas' }

export function useHouseholdMembers() {
  return useQuery({
    queryKey: ['household-members'],
    queryFn: () => apiGet<HouseholdMember[]>('/api/household/members'),
    staleTime: 5 * 60 * 1000,
  })
}

export function useShareState(entity: ShareEntity, id: number | null, enabled: boolean) {
  return useQuery({
    queryKey: ['share', entity, id],
    enabled: enabled && id != null,
    queryFn: () => apiGet<ShareState>(`/api/share?entity=${entity}&id=${id}`),
  })
}

interface ShareBody {
  id: number
  shared?: 0 | 1
  members?: number[]
}

export function useShareMutation(entity: ShareEntity) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (b: ShareBody) => apiPost<ShareState & { ok: boolean }>('/api/share', { entity, ...b }),
    onSuccess: (_data, vars) => {
      // Consistencia: refrescar el listado afectado y el estado de compartido de este ítem.
      qc.invalidateQueries({ queryKey: [LIST_KEY[entity]] })
      qc.invalidateQueries({ queryKey: ['share', entity, vars.id] })
    },
  })
}
