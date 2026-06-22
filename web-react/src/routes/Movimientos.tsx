import { useState } from 'react'
import { useTransactions, useTxMutations } from '../hooks/useTransactions'
import { type TxFilters } from '../hooks/useTransactions'
import { useAccounts } from '../hooks/useAccounts'
import { useCategories } from '../hooks/useCategories'
import { formatMoney } from '../lib/format'
import Skeleton from '../components/ui/Skeleton'
import EmptyState from '../components/ui/EmptyState'

const PERIODS = ['hoy', 'semana', 'mes', 'mes pasado', 'año']

export default function Movimientos() {
  const [filters, setFilters] = useState<TxFilters>({ period: 'mes' })
  const { data, isLoading } = useTransactions(filters)
  const accounts = useAccounts()
  const categories = useCategories()
  const { remove } = useTxMutations()

  return (
    <div style={{ padding: '14px 18px 24px' }}>
      <div className="cap" style={{ marginBottom: 12 }}>Movimientos</div>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 16 }}>
        <select value={filters.period} onChange={(e) => setFilters((f) => ({ ...f, period: e.target.value }))} style={sel}>
          {PERIODS.map((p) => <option key={p} value={p}>{p}</option>)}
        </select>
        <select value={filters.account_id ?? ''} onChange={(e) => setFilters((f) => ({ ...f, account_id: e.target.value ? Number(e.target.value) : undefined }))} style={sel}>
          <option value="">Toda cuenta</option>
          {accounts.data?.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
        </select>
        <select value={filters.category_id ?? ''} onChange={(e) => setFilters((f) => ({ ...f, category_id: e.target.value ? Number(e.target.value) : undefined }))} style={sel}>
          <option value="">Toda categoría</option>
          {categories.data?.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
        <input placeholder="Buscar…" value={filters.q ?? ''} onChange={(e) => setFilters((f) => ({ ...f, q: e.target.value }))} style={{ ...sel, flex: 1 }} />
      </div>

      {isLoading && <div style={{ display: 'grid', gap: 8 }}>{[0, 1, 2].map((i) => <Skeleton key={i} h={44} />)}</div>}
      {data && data.length === 0 && <EmptyState>Sin movimientos para este filtro.</EmptyState>}
      {data?.map((t) => (
        <div key={t.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '12px 0', borderBottom: '1px solid var(--color-mist)' }}>
          <span>
            <span style={{ fontSize: 14, fontWeight: 500 }}>{t.description}</span><br />
            <span style={{ fontSize: 11, color: 'var(--color-sage)' }}>{t.category_name ?? 'sin categoría'} · {t.account_name ?? ''} · {t.occurred_at.slice(0, 10)}</span>
          </span>
          <span style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <span style={{ fontSize: 15, fontWeight: 500, color: t.type === 'ingreso' ? '#3b6d11' : 'var(--color-obsidian-ink)' }}>
              {t.type === 'ingreso' ? '+' : '−'}{formatMoney(t.amount, t.currency)}
            </span>
            <button aria-label={`Borrar ${t.description}`} onClick={() => remove.mutate(t.id)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--color-sage)' }}>
              <i className="ti ti-trash" aria-hidden />
            </button>
          </span>
        </div>
      ))}
    </div>
  )
}

const sel: React.CSSProperties = { border: '1px solid var(--color-mist)', borderRadius: 9999, padding: '6px 12px', fontSize: 13, background: 'transparent' }
