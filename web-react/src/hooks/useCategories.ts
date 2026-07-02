import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiGet, apiPost, apiPatch, apiDelete } from '../lib/api'
import { notifyOk, notifyErr } from '../lib/notify'
import { type Category } from '../lib/types'
export function useCategories() {
  return useQuery({ queryKey: ['categories'], queryFn: () => apiGet<Category[]>('/api/categories') })
}
export function useCategoryMutations() {
  const qc = useQueryClient()
  const inval = () => qc.invalidateQueries({ queryKey: ['categories'] })
  return {
    create: useMutation({ mutationFn: (b: Partial<Category>) => apiPost('/api/categories', b), onSuccess: () => { inval(); notifyOk('Categoría creada') }, onError: notifyErr }),
    update: useMutation({ mutationFn: ({ id, ...b }: { id: number } & Partial<Category>) => apiPatch(`/api/categories/${id}`, b), onSuccess: () => { inval(); notifyOk('Categoría actualizada') }, onError: notifyErr }),
    remove: useMutation({ mutationFn: (id: number) => apiDelete(`/api/categories/${id}`), onSuccess: () => { inval(); notifyOk('Categoría eliminada') }, onError: notifyErr }),
  }
}
