export type Currency = 'ARS' | 'USD' | 'EUR'

export interface Me {
  id: number
  name: string
  username: string
  color?: string
  scope: string
  others: { name: string; scope_value: string }[]
}

export interface Balance { currency: Currency; balance: number }

export interface Account {
  id: number
  name: string
  type: 'efectivo' | 'billetera' | 'credito' | 'banco' | 'inversion'
  color?: string
  icon?: string
  active: number
  closing_day?: number | null
  due_day?: number | null
  balances?: Balance[]
}

export interface CategoryTotal { cat: string; color?: string; total: number }

export interface HoyItem { tipo: string; titulo: string; sub: string; hora: string }

export interface Overview2Kpis {
  gasto_mes: number
  gasto_prev_alt: number
  ingreso_mes: number
  deuda_tarjetas: number
  cuotas_futuras: number
  cuotas_n: number
  disponible: number
}

export interface Overview2 {
  patrimonio_ars: number
  patrimonio_usd: number | null
  blue: number
  kpis: Overview2Kpis
  cashflow: { ym: string; ingresos: number; gastos: number }[]
  hoy: HoyItem[]
  por_categoria: CategoryTotal[]
  mes_nombre?: string
  year?: number
  dia?: number
}

export interface Transaction {
  id: number
  type: 'gasto' | 'ingreso'
  amount: number
  currency: Currency
  description: string
  occurred_at: string
  account_id: number
  account_name?: string
  category_id?: number | null
  category_name?: string | null
  acc_name?: string | null
  cat_name?: string | null
}

export interface Category {
  id: number
  name: string
  color?: string
  icon?: string
}

export interface Recurring {
  id: number
  description: string
  amount: number
  currency: Currency
  account_id: number
  next_occurrence: string
  active: number
  total_installments?: number | null
  installments_fired?: number | null
}

export interface CicloTotal { currency: Currency; total: number }

export interface VencimientoCard {
  account_id: number
  account_name: string
  icon?: string | null
  user_id?: number
  last_closing?: string
  next_closing?: string
  next_due?: string
  ciclo_cerrado: CicloTotal[]
  ciclo_abierto: CicloTotal[]
  error?: string
}

// ---- Assistant section types ----

export interface Tarea {
  id: number
  text: string
  priority: 'alta' | 'media' | 'baja'
  due_at?: string | null
  user_id: number
  created_at: string
  status: 'pendiente' | 'hecha'
  completed_at?: string | null
  shared?: number
}

export interface Nota {
  id: number
  text: string
  tags: string[]
  user_id: number
  created_at: string
  shared?: number
}

export interface HabitoLog {
  id: number
  name: string
  value?: number | null
  unit?: string | null
  note?: string | null
  logged_at: string
  user_id: number
}

export interface HabitoResumen {
  name: string
  cnt: number
  total: number
  unit?: string | null
}

export interface HabitosResponse {
  items: HabitoLog[]
  resumen: HabitoResumen[]
  days: number
}

export interface ListaItem {
  id: number
  text: string
  done: number
  qty?: number | null
  unit?: string | null
  category?: string | null
}

export interface Lista {
  id: number
  name: string
  icon?: string | null
  kind?: string | null
  target_date?: string | null
  recurrence?: string | null
  items: ListaItem[]
  pend: number
  total: number
}

export interface ListaTemplate {
  id: number
  name: string
  icon?: string | null
  total: number
}

export interface Evento {
  id: number
  title: string
  starts_at: string
  location?: string | null
  notes?: string | null
  kind?: string | null
  user_id: number
  reminders?: Recordatorio[]
}

export interface Recordatorio {
  id: number
  text: string
  remind_at: string
  fired: number
  source?: string | null
  event_id?: number | null
  user_id: number
}
