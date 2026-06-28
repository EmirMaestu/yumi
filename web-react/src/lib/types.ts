export type Currency = 'ARS' | 'USD' | 'EUR'

export interface Me {
  id: number
  name: string
  username: string
  color?: string
  scope: string
  others: { name: string; scope_value: string }[]
  is_admin?: boolean
  share_all?: boolean
}

export interface AdminModelRow {
  model: string
  calls: number
  input_tokens: number
  output_tokens: number
  cache_read: number
  cost_usd: number
}

export interface AdminKindRow { kind: string; calls: number; cost_usd: number }

export interface AdminOverview {
  users_total: number
  users_active: number
  cost_today: number
  cost_month: number
  cost_today_system: number
  cost_month_system: number
  msgs_today: number
  calls_today: number
  by_model: AdminModelRow[]
  by_kind: AdminKindRow[]
  caps: { daily_global_usd: number; free_daily_msgs: number }
  usage_ready: boolean
}

export interface AdminUser {
  id: number
  name: string
  username: string
  telegram_id: number
  active: number
  created_at: string
  plan: string
  is_admin: boolean
  msgs_today: number
  cost_month: number
}

export interface AdminUsersResponse {
  users: AdminUser[]
  usage_ready: boolean
  plans: string[]
}

export interface AdminReferral {
  id: number
  name: string
  username: string
  referral_code: string | null
  invite_link: string | null
  invite_link_wa: string | null
  invited_count: number
  referred_by_name: string | null
}

export interface AdminReferralsResponse {
  ready: boolean
  users: AdminReferral[]
  bot_username: string
}

export interface AdminHouseholdMember {
  id: number
  name: string
  username: string
  plan: string
  active: number
}

export interface AdminHousehold {
  household_id: number
  plan: string
  cap: number
  daily_msgs: number
  size: number
  members: AdminHouseholdMember[]
}

export interface AdminHouseholdsResponse {
  households: AdminHousehold[]
}

export interface Balance { currency: Currency; balance: number }

export interface Account {
  id: number
  name: string
  type: 'efectivo' | 'billetera' | 'debito' | 'credito' | 'banco' | 'dolares' | 'cripto' | 'inversion'
  color?: string
  icon?: string
  active: number
  closing_day?: number | null
  due_day?: number | null
  shared?: number
  balances?: Balance[]
}

export interface CategoryTotal { cat: string; color?: string; total: number }

export interface HoyItem { tipo: string; titulo: string; sub: string; hora: string; avisos?: string[] }

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
  description?: string | null
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
