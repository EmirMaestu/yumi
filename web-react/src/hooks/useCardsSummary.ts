import { useQuery } from '@tanstack/react-query'
import { apiGet } from '../lib/api'

// Fuente única de la matemática de tarjetas (server-side, D2). Reemplaza a las
// fórmulas de cards.ts; la migración de las pantallas de tarjetas es incremental.
export interface CardSummary {
  account_id: number
  name: string
  consumos: number
  en_cuotas: number
  deuda_total: number
  resumen_cerrado: number
  proximo_resumen: number
  cuotas_mes: number
  next_closing: string | null
  next_due: string | null
  credit_limit: number | null
  disponible: number | null
}

export function useCardsSummary() {
  return useQuery({ queryKey: ['cards-summary'], queryFn: () => apiGet<CardSummary[]>('/api/cards/summary') })
}
