import { useQuery } from '@tanstack/react-query'
import { apiGet } from '../lib/api'

export interface StatementSummary { year: number; month: number; gasto_total: number; vs_prev_pct: number | null }
export interface StatementDetail {
  year: number
  month: number
  gasto_total: number
  ingreso_total: number
  n_movimientos: number
  por_categoria: { name: string; total: number }[]
  por_cuenta: { name: string; neto: number }[]
  tarjetas: { name: string; resumen_cerrado: number }[]
  vs_prev_pct: number | null
}

export function useStatements() {
  return useQuery({ queryKey: ['statements'], queryFn: () => apiGet<StatementSummary[]>('/api/statements') })
}

export function useStatement(year: number, month: number) {
  return useQuery({
    queryKey: ['statement', year, month],
    queryFn: () => apiGet<StatementDetail>(`/api/statements/${year}/${month}`),
    retry: false,
  })
}
