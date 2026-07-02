import { useQuery } from '@tanstack/react-query'
import { apiGet } from '../lib/api'

export interface MonthlyTrend {
  labels: string[]
  series: { gasto: Record<string, number[]>; ingreso: Record<string, number[]> }
}
export interface CategoryTrend {
  labels: string[]
  series: Record<string, number[]>
}

export function useMonthlyTrend(months: number) {
  return useQuery({
    queryKey: ['trends', 'total', months],
    queryFn: () => apiGet<MonthlyTrend>(`/api/trends?months=${months}&by=total`),
  })
}

export function useCategoryTrend(months: number) {
  return useQuery({
    queryKey: ['trends', 'category', months],
    queryFn: () => apiGet<CategoryTrend>(`/api/trends?months=${months}&by=category`),
  })
}
