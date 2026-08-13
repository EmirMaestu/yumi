import { useMutation, useQuery, useInfiniteQuery, useQueryClient } from '@tanstack/react-query'
import { apiGet, apiPost, apiPatch, apiDelete } from '../lib/api'
import { notifyOk, notifyErr, notifyUndo } from '../lib/notify'
import { formatMoney } from '../lib/format'
import type { Transaction, Currency, TxKind } from '../lib/types'

// Filtros explícitos: year/month (mes navegable), date_from/date_to (rango), o nada (todo).
export interface TxFilters {
  year?: number
  month?: number
  date_from?: string
  date_to?: string
  account_id?: number
  category_id?: number
  currency?: string
  type?: 'gasto' | 'ingreso'
  q?: string
}

export interface TxSum { type: 'gasto' | 'ingreso'; currency: Currency; kind: TxKind; total: number }
export interface TxPage { items: Transaction[]; total: number; sums: TxSum[] }

function buildQuery(filters: TxFilters, offset?: number, limit?: number): string {
  const qs = new URLSearchParams()
  if (filters.date_from || filters.date_to) {
    if (filters.date_from) qs.set('date_from', filters.date_from)
    if (filters.date_to) qs.set('date_to', filters.date_to)
  } else if (filters.year && filters.month) {
    qs.set('year', String(filters.year)); qs.set('month', String(filters.month))
  } else if (filters.year) {
    qs.set('year', String(filters.year))
  }
  if (filters.account_id) qs.set('account_id', String(filters.account_id))
  if (filters.category_id) qs.set('category_id', String(filters.category_id))
  if (filters.currency) qs.set('currency', filters.currency)
  if (filters.type) qs.set('type', filters.type)
  if (filters.q) qs.set('q', filters.q)
  if (offset) qs.set('offset', String(offset))
  if (limit) qs.set('limit', String(limit))
  return qs.toString()
}

export function useTransactions(filters: TxFilters = {}) {
  const query = buildQuery(filters)
  return useQuery({
    queryKey: ['transactions', filters],
    queryFn: () => apiGet<TxPage>(`/api/transactions${query ? `?${query}` : ''}`),
  })
}

// Paginación con offset para el historial navegable (BF7/UX13). La invalidación
// de ['transactions'] por las mutaciones también refresca esta query.
export function useTransactionsInfinite(filters: TxFilters = {}, pageSize = 50) {
  return useInfiniteQuery({
    queryKey: ['transactions', 'infinite', filters],
    queryFn: ({ pageParam }) => apiGet<TxPage>(`/api/transactions?${buildQuery(filters, pageParam, pageSize)}`),
    initialPageParam: 0,
    getNextPageParam: (lastPage, allPages) => {
      const loaded = allPages.reduce((n, p) => n + p.items.length, 0)
      return loaded < lastPage.total ? loaded : undefined
    },
  })
}

export interface TransferBody {
  from_account_id: number
  to_account_id: number
  amount: number
  currency?: string
  occurred_at?: string
  description?: string
}

export function useTransferMutation(okMsg = 'Transferencia registrada') {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (b: TransferBody) => apiPost('/api/transfers', b),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['transactions'] })
      qc.invalidateQueries({ queryKey: ['overview2'] })
      qc.invalidateQueries({ queryKey: ['accounts-balances'] })
      qc.invalidateQueries({ queryKey: ['vencimientos'] })
      notifyOk(okMsg)
    },
    onError: notifyErr,
  })
}

interface DeleteResult { ok: boolean; trash_ids: number[] }

// Carga rápida de gasto (teclado numérico del Inicio, diseño 1c/1d): crea el gasto
// y ofrece "Deshacer" por 10s borrando el movimiento recién creado. Reutiliza las
// mismas invalidaciones que useTxMutations; el borrado del undo es directo (sin su
// propio toast de papelera, para no encadenar deshacer-sobre-deshacer).
export function useQuickExpense() {
  const qc = useQueryClient()
  const inval = () => { qc.invalidateQueries({ queryKey: ['transactions'] }); qc.invalidateQueries({ queryKey: ['overview2'] }); qc.invalidateQueries({ queryKey: ['accounts-balances'] }); qc.invalidateQueries({ queryKey: ['vencimientos'] }) }
  return useMutation({
    mutationFn: (b: Partial<Transaction>) => apiPost<{ id: number }>('/api/transactions', b),
    onSuccess: (data, vars) => {
      inval()
      const money = formatMoney(Number(vars.amount) || 0, (vars.currency as Currency) ?? 'ARS')
      const id = data?.id
      if (id) notifyUndo(`Gasto de ${money} guardado`, () => { apiDelete(`/api/transactions/${id}`).catch(() => {}).finally(inval) })
      else notifyOk('Gasto guardado')
    },
    onError: notifyErr,
  })
}

export function useTxMutations() {
  const qc = useQueryClient()
  const inval = () => { qc.invalidateQueries({ queryKey: ['transactions'] }); qc.invalidateQueries({ queryKey: ['overview2'] }); qc.invalidateQueries({ queryKey: ['accounts-balances'] }); qc.invalidateQueries({ queryKey: ['vencimientos'] }) }
  // Restaura desde la papelera (undo de un borrado). BF12/UX7.
  const restore = useMutation({
    mutationFn: (trashId: number) => apiPost(`/api/transactions/restore/${trashId}`),
    onSuccess: () => { inval(); notifyOk('Movimiento restaurado') },
    onError: notifyErr,
  })
  const plural = (n: number, w: string) => `${n} ${w}${n === 1 ? '' : 's'}`
  return {
    restore,
    create: useMutation({ mutationFn: (b: Partial<Transaction>) => apiPost('/api/transactions', b), onSuccess: () => { inval(); notifyOk('Movimiento guardado') }, onError: notifyErr }),
    update: useMutation({ mutationFn: ({ id, ...b }: { id: number } & Partial<Transaction>) => apiPatch(`/api/transactions/${id}`, b), onSuccess: () => { inval(); notifyOk('Movimiento actualizado') }, onError: notifyErr }),
    remove: useMutation({
      mutationFn: (id: number) => apiDelete<DeleteResult>(`/api/transactions/${id}`),
      // Optimista (UX8): la fila desaparece ya; rollback si falla.
      onMutate: async (id: number) => {
        await qc.cancelQueries({ queryKey: ['transactions'] })
        const prev = qc.getQueriesData({ queryKey: ['transactions'] })
        qc.setQueriesData({ queryKey: ['transactions'] }, (old) => {
          const o = old as { pages?: { items: Transaction[] }[]; items?: Transaction[] } | undefined
          if (!o) return o
          if (o.pages) return { ...o, pages: o.pages.map((p) => ({ ...p, items: p.items.filter((t) => t.id !== id) })) }
          if (o.items) return { ...o, items: o.items.filter((t) => t.id !== id) }
          return o
        })
        return { prev }
      },
      onError: (e, _id, ctx) => {
        (ctx as { prev?: [readonly unknown[], unknown][] } | undefined)?.prev?.forEach(([k, v]) => qc.setQueryData(k as readonly unknown[], v))
        notifyErr(e)
      },
      onSuccess: (data) => {
        const tid = data?.trash_ids?.[0]
        if (tid) notifyUndo('Movimiento eliminado', () => restore.mutate(tid))
        else notifyOk('Movimiento eliminado')
      },
      onSettled: () => inval(),
    }),
    bulkDelete: useMutation({
      mutationFn: (ids: number[]) => apiPost<DeleteResult>('/api/transactions/bulk_delete', { ids }),
      onSuccess: (data, ids) => {
        inval()
        const trashIds = data?.trash_ids ?? []
        if (trashIds.length) notifyUndo(`${plural(ids.length, 'movimiento')} eliminado${ids.length === 1 ? '' : 's'}`, () => trashIds.forEach((t) => restore.mutate(t)))
        else notifyOk(`${plural(ids.length, 'movimiento')} eliminado${ids.length === 1 ? '' : 's'}`)
      },
      onError: notifyErr,
    }),
    bulkMove: useMutation({ mutationFn: (b: { ids: number[]; account_id: number }) => apiPost('/api/transactions/bulk_move', b), onSuccess: (_d, b) => { inval(); notifyOk(`${plural(b.ids.length, 'movimiento')} movido${b.ids.length === 1 ? '' : 's'}`) }, onError: notifyErr }),
    bulkUpdate: useMutation({ mutationFn: (b: { ids: number[]; category_id: number }) => apiPost('/api/transactions/bulk_update', b), onSuccess: (_d, b) => { inval(); notifyOk(`${plural(b.ids.length, 'movimiento')} recategorizado${b.ids.length === 1 ? '' : 's'}`) }, onError: notifyErr }),
  }
}
