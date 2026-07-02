import { useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import * as Checkbox from '@radix-ui/react-checkbox'
import { useTransactionsInfinite, useTxMutations, type TxFilters } from '../hooks/useTransactions'
import { useAccounts } from '../hooks/useAccounts'
import { useCategories } from '../hooks/useCategories'
import { formatMonthLabel, formatDayHeader, todayISODate } from '../lib/format'
import { Money } from '../lib/privacy'
import { type Transaction } from '../lib/types'
import { MovimientosSkeleton } from '../components/ui/skeletons'
import EmptyState from '../components/ui/EmptyState'
import BackButton from '../components/ui/BackButton'
import Select from '../components/ui/Select'
import Modal from '../components/ui/Modal'
import ConfirmDialog from '../components/ui/ConfirmDialog'
import EditTxModal from '../components/EditTxModal'
import TxDetailSheet from '../components/TxDetailSheet'

type Period =
  | { mode: 'month'; year: number; month: number }
  | { mode: 'year'; year: number }
  | { mode: 'all' }
  | { mode: 'range'; from: string; to: string }

const PRESET_OPTS = [
  { value: 'month', label: 'Este mes' },
  { value: 'prev', label: 'Mes pasado' },
  { value: 'year', label: 'Este año' },
  { value: 'all', label: 'Todo' },
  { value: 'range', label: 'Rango…' },
]

function currentMonth(): Period {
  const n = new Date()
  return { mode: 'month', year: n.getFullYear(), month: n.getMonth() + 1 }
}

export default function Movimientos() {
  const [sp] = useSearchParams()
  const [period, setPeriod] = useState<Period>(currentMonth)
  const [account_id, setAccountId] = useState<number | undefined>(() => {
    const a = sp.get('account_id'); return a ? Number(a) : undefined
  })
  const [category_id, setCategoryId] = useState<number | undefined>(() => {
    const c = sp.get('category_id'); return c ? Number(c) : undefined
  })
  const [q, setQ] = useState('')
  const type = sp.get('type') === 'ingreso' ? 'ingreso' : sp.get('type') === 'gasto' ? 'gasto' : undefined

  const filters: TxFilters = useMemo(() => {
    const base: TxFilters = { account_id, category_id, type, q: q || undefined }
    if (period.mode === 'month') return { ...base, year: period.year, month: period.month }
    if (period.mode === 'year') return { ...base, year: period.year }
    if (period.mode === 'range') return { ...base, date_from: period.from, date_to: period.to }
    return base
  }, [period, account_id, category_id, type, q])

  const { data, isLoading, fetchNextPage, hasNextPage, isFetchingNextPage } = useTransactionsInfinite(filters)
  const accounts = useAccounts()
  const categories = useCategories()
  const { remove, bulkDelete, bulkMove, bulkUpdate } = useTxMutations()

  const items = useMemo(() => data?.pages.flatMap((p) => p.items) ?? [], [data])
  const total = data?.pages[0]?.total ?? 0
  const sums = data?.pages[0]?.sums ?? []
  const sumBy = (type: 'gasto' | 'ingreso') =>
    sums.filter((s) => s.kind === 'normal' && s.type === type && s.currency === 'ARS').reduce((a, s) => a + s.total, 0)
  const totalGastos = sumBy('gasto')
  const totalIngresos = sumBy('ingreso')

  // Agrupación por día, preservando el orden desc.
  const groups = useMemo(() => {
    const map: { day: string; items: Transaction[] }[] = []
    for (const t of items) {
      const day = t.occurred_at.slice(0, 10)
      const last = map[map.length - 1]
      if (last && last.day === day) last.items.push(t)
      else map.push({ day, items: [t] })
    }
    return map
  }, [items])
  const daySubtotal = (rows: Transaction[]) =>
    rows.filter((t) => (t.kind ?? 'normal') === 'normal' && t.type === 'gasto' && t.currency === 'ARS')
      .reduce((a, t) => a + t.amount, 0)

  // Selección + modales
  const [selectMode, setSelectMode] = useState(false)
  const [sel, setSel] = useState<Set<number>>(new Set())
  const toggleSel = (id: number) => setSel((prev) => {
    const next = new Set(prev); next.has(id) ? next.delete(id) : next.add(id); return next
  })
  const [moveOpen, setMoveOpen] = useState(false)
  const [moveAccountId, setMoveAccountId] = useState<string | undefined>(undefined)
  const [catOpen, setCatOpen] = useState(false)
  const [catId, setCatId] = useState<string | undefined>(undefined)
  const [bulkDeleteOpen, setBulkDeleteOpen] = useState(false)
  const [editTx, setEditTx] = useState<Transaction | null>(null)
  const [detailTx, setDetailTx] = useState<Transaction | null>(null)

  const accountOpts = [{ value: 'all', label: 'Toda cuenta' }, ...(accounts.data ?? []).map((a) => ({ value: String(a.id), label: a.name }))]
  const categoryOpts = [{ value: 'all', label: 'Toda categoría' }, ...(categories.data ?? []).map((c) => ({ value: String(c.id), label: c.name }))]
  const moveAccountOpts = (accounts.data ?? []).map((a) => ({ value: String(a.id), label: a.name }))

  // Navegador de mes
  const now = new Date()
  const atCurrentMonth = period.mode === 'month' && period.year === now.getFullYear() && period.month === now.getMonth() + 1
  const stepMonth = (delta: number) => setPeriod((p) => {
    if (p.mode !== 'month') return p
    const d = new Date(p.year, p.month - 1 + delta, 1)
    return { mode: 'month', year: d.getFullYear(), month: d.getMonth() + 1 }
  })
  const onPreset = (v: string) => {
    if (v === 'month') setPeriod(currentMonth())
    else if (v === 'prev') { const d = new Date(now.getFullYear(), now.getMonth() - 1, 1); setPeriod({ mode: 'month', year: d.getFullYear(), month: d.getMonth() + 1 }) }
    else if (v === 'year') setPeriod({ mode: 'year', year: now.getFullYear() })
    else if (v === 'all') setPeriod({ mode: 'all' })
    else if (v === 'range') setPeriod({ mode: 'range', from: todayISODate(), to: todayISODate() })
  }
  const presetValue = period.mode === 'month' ? 'month' : period.mode

  // Export CSV
  const exportHref = period.mode === 'month'
    ? `/api/export.csv?year=${period.year}&month=${period.month}`
    : '/api/export.csv'

  return (
    <div style={{ padding: '14px 18px 24px' }}>
      <div style={{ display: 'flex', alignItems: 'center', marginBottom: 12 }}>
        <BackButton />
        <div className="cap" style={{ flex: 1 }}>Movimientos</div>
        <a href={exportHref} download style={{ ...selectModeBtn, textDecoration: 'none', marginRight: 6, display: 'inline-flex', alignItems: 'center', gap: 4 }}>
          <i className="ti ti-download" aria-hidden /> Exportar
        </a>
        {!selectMode
          ? <button onClick={() => setSelectMode(true)} style={selectModeBtn}>Seleccionar</button>
          : <button onClick={() => { setSelectMode(false); setSel(new Set()) }} style={selectModeBtn}>Cancelar</button>}
      </div>

      {/* Período: navegador de mes + presets */}
      <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 12, flexWrap: 'wrap' }}>
        {period.mode === 'month' && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <button onClick={() => stepMonth(-1)} aria-label="Mes anterior" style={navBtn}>‹</button>
            <span style={{ fontSize: 14, fontWeight: 500, minWidth: 120, textAlign: 'center', textTransform: 'capitalize' }}>
              {formatMonthLabel(period.year, period.month)}
            </span>
            <button onClick={() => stepMonth(1)} disabled={atCurrentMonth} aria-label="Mes siguiente" style={{ ...navBtn, opacity: atCurrentMonth ? 0.35 : 1 }}>›</button>
          </div>
        )}
        <Select value={presetValue} onValueChange={onPreset} options={PRESET_OPTS} ariaLabel="Período" />
      </div>

      {period.mode === 'range' && (
        <div style={{ display: 'flex', gap: 8, marginBottom: 12, alignItems: 'center' }}>
          <input type="date" value={period.from} onChange={(e) => setPeriod({ mode: 'range', from: e.target.value, to: period.to })} style={dateInput} />
          <span style={{ color: 'var(--color-sage)' }}>→</span>
          <input type="date" value={period.to} onChange={(e) => setPeriod({ mode: 'range', from: period.from, to: e.target.value })} style={dateInput} />
        </div>
      )}

      {/* Filtros cuenta/categoría/búsqueda */}
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 16 }}>
        <Select value={account_id ? String(account_id) : 'all'} onValueChange={(v) => setAccountId(v === 'all' ? undefined : Number(v))} options={accountOpts} ariaLabel="Cuenta" />
        <Select value={category_id ? String(category_id) : 'all'} onValueChange={(v) => setCategoryId(v === 'all' ? undefined : Number(v))} options={categoryOpts} ariaLabel="Categoría" />
        <input placeholder="Buscar…" value={q} onChange={(e) => setQ(e.target.value)}
          style={{ border: '1px solid var(--color-mist)', borderRadius: 10, padding: '9px 12px', fontSize: 14, background: 'var(--color-linen)', flex: 1, minWidth: 120 }} />
      </div>

      {/* Totales del filtro (UX5) */}
      {!isLoading && items.length > 0 && (
        <div style={{ position: 'sticky', top: 0, zIndex: 10, background: 'var(--color-linen)', padding: '4px 0 10px', fontSize: 12.5, color: 'var(--color-sage)', borderBottom: '1px solid var(--color-mist)', marginBottom: 8 }}>
          Gastos <b style={{ color: 'var(--color-obsidian-ink)' }}><Money value={totalGastos} /></b>
          {' · '}Ingresos <b style={{ color: 'var(--color-obsidian-ink)' }}><Money value={totalIngresos} /></b>
          {' · '}{total} movimiento{total === 1 ? '' : 's'}
        </div>
      )}

      {/* Selection toolbar */}
      {sel.size > 0 && (
        <div style={{ position: 'sticky', top: 0, zIndex: 20, display: 'flex', alignItems: 'center', gap: 10, padding: '10px 0', borderBottom: '1px solid var(--color-mist)', background: 'var(--color-linen)', marginBottom: 8 }}>
          <span style={{ fontSize: 14, fontWeight: 500, flex: 1 }}>{sel.size} seleccionado{sel.size === 1 ? '' : 's'}</span>
          <button onClick={() => setMoveOpen(true)} style={ghostBtn}>Mover</button>
          <button onClick={() => setCatOpen(true)} style={ghostBtn}>Categoría</button>
          <button onClick={() => setBulkDeleteOpen(true)} style={ghostBtn}>Borrar</button>
          <button onClick={() => setSel(new Set())} aria-label="Limpiar selección" style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 18, color: 'var(--color-sage)' }}>×</button>
        </div>
      )}

      {isLoading && <MovimientosSkeleton />}
      {!isLoading && items.length === 0 && <EmptyState>Sin movimientos para este filtro.</EmptyState>}

      {groups.map((g) => (
        <div key={g.day}>
          <div style={{ position: 'sticky', top: 36, zIndex: 5, display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', background: 'var(--color-linen)', padding: '8px 0 4px' }}>
            <span className="cap" style={{ fontSize: 11, textTransform: 'capitalize' }}>{formatDayHeader(g.day)}</span>
            <span style={{ fontSize: 11, color: 'var(--color-sage)' }}>−<Money value={daySubtotal(g.items)} /></span>
          </div>
          {g.items.map((t) => {
            const isTransfer = t.kind === 'transfer' || t.kind === 'card_payment'
            return (
              <div key={t.id} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '12px 0', borderBottom: '1px solid var(--color-mist)' }}>
                {selectMode && (
                  <Checkbox.Root checked={sel.has(t.id)} onCheckedChange={() => toggleSel(t.id)} aria-label={`Seleccionar ${t.description}`}
                    style={{ width: 18, height: 18, border: '1px solid var(--color-mist)', borderRadius: 5, background: sel.has(t.id) ? 'var(--color-voltage)' : 'transparent', display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer', flexShrink: 0 }}>
                    <Checkbox.Indicator><i className="ti ti-check" style={{ fontSize: 13, color: 'var(--voltage-on-dark)' }} aria-hidden /></Checkbox.Indicator>
                  </Checkbox.Root>
                )}
                <span style={{ flex: 1, minWidth: 0, cursor: 'pointer' }} onClick={() => setDetailTx(t)}>
                  <span style={{ fontSize: 14, fontWeight: 500 }}>{t.description}</span><br />
                  <span style={{ fontSize: 11, color: 'var(--color-sage)', display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                    {!isTransfer && t.cat_color && <span style={{ width: 7, height: 7, borderRadius: '50%', background: t.cat_color, display: 'inline-block' }} />}
                    {!isTransfer && t.cat_icon ? `${t.cat_icon} ` : ''}
                    {isTransfer ? (t.kind === 'card_payment' ? 'Pago de tarjeta' : 'Transferencia') : (t.cat_name ?? 'sin categoría')} · {t.acc_name ?? ''}
                  </span>
                </span>
                <span style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
                  <span style={{ fontSize: 15, fontWeight: 500, color: isTransfer ? 'var(--color-sage)' : (t.type === 'ingreso' ? '#3b6d11' : 'var(--color-obsidian-ink)') }}>
                    {isTransfer ? <i className="ti ti-arrows-left-right" aria-hidden style={{ marginRight: 3 }} /> : (t.type === 'ingreso' ? '+' : '−')}<Money value={t.amount} currency={t.currency} />
                  </span>
                  {!isTransfer && (
                    <button aria-label={`Editar ${t.description}`} onClick={() => setEditTx(t)} style={iconBtn}><i className="ti ti-edit" aria-hidden /></button>
                  )}
                  <button aria-label={`Borrar ${t.description}`} onClick={() => remove.mutate(t.id)} style={iconBtn}><i className="ti ti-trash" aria-hidden /></button>
                </span>
              </div>
            )
          })}
        </div>
      ))}

      {/* Paginación visible (BF7) */}
      {!isLoading && items.length > 0 && (
        <div style={{ textAlign: 'center', padding: '16px 0 4px', fontSize: 12, color: 'var(--color-sage)' }}>
          {hasNextPage
            ? <button onClick={() => fetchNextPage()} disabled={isFetchingNextPage} style={ghostBtn}>{isFetchingNextPage ? 'Cargando…' : 'Cargar más'}</button>
            : null}
          <div style={{ marginTop: 8 }}>Mostrando {items.length} de {total}</div>
        </div>
      )}

      {/* Bulk move modal */}
      <Modal open={moveOpen} onClose={() => setMoveOpen(false)} title="Mover a cuenta">
        <div style={{ display: 'grid', gap: 12 }}>
          <Select value={moveAccountId} onValueChange={setMoveAccountId} options={moveAccountOpts} placeholder="Seleccionar cuenta…" ariaLabel="Cuenta destino" style={{ width: '100%' }} />
          <button onClick={() => { if (!moveAccountId) return; bulkMove.mutate({ ids: [...sel], account_id: Number(moveAccountId) }); setSel(new Set()); setMoveOpen(false) }} style={ctaBtn}>
            Mover {sel.size} movimiento{sel.size === 1 ? '' : 's'} →
          </button>
        </div>
      </Modal>

      {/* Bulk categorize modal */}
      <Modal open={catOpen} onClose={() => setCatOpen(false)} title="Cambiar categoría">
        <div style={{ display: 'grid', gap: 12 }}>
          <Select value={catId} onValueChange={setCatId} options={(categories.data ?? []).map((c) => ({ value: String(c.id), label: c.name }))} placeholder="Seleccionar categoría…" ariaLabel="Categoría" style={{ width: '100%' }} />
          <button onClick={() => { if (!catId) return; bulkUpdate.mutate({ ids: [...sel], category_id: Number(catId) }); setSel(new Set()); setCatOpen(false) }} style={ctaBtn}>
            Cambiar {sel.size} movimiento{sel.size === 1 ? '' : 's'} →
          </button>
        </div>
      </Modal>

      {/* Bulk delete confirm */}
      <ConfirmDialog open={bulkDeleteOpen} onOpenChange={setBulkDeleteOpen}
        title={`¿Borrar ${sel.size} movimiento${sel.size === 1 ? '' : 's'}?`}
        description="Esta acción no se puede deshacer."
        onConfirm={() => { bulkDelete.mutate([...sel]); setSel(new Set()); setBulkDeleteOpen(false) }} />

      {/* Per-row edit modal */}
      <EditTxModal key={editTx ? `tx-${editTx.id}` : 'tx-edit'} tx={editTx} open={editTx !== null} onClose={() => setEditTx(null)} />

      {/* Detalle del movimiento (tap en la fila) */}
      <TxDetailSheet tx={detailTx} open={detailTx !== null} onClose={() => setDetailTx(null)} onEdit={setEditTx} />
    </div>
  )
}

const iconBtn: React.CSSProperties = { background: 'none', border: 'none', cursor: 'pointer', color: 'var(--color-sage)', fontSize: 16, padding: 2 }
const ghostBtn: React.CSSProperties = { background: 'transparent', border: '1px solid var(--color-mist)', borderRadius: 10, padding: '7px 14px', fontSize: 13, cursor: 'pointer' }
const ctaBtn: React.CSSProperties = { background: 'var(--color-voltage)', color: 'var(--voltage-on-dark)', border: 'none', borderRadius: 10, padding: '14px', fontWeight: 500, cursor: 'pointer' }
const selectModeBtn: React.CSSProperties = { background: 'transparent', border: 'none', cursor: 'pointer', color: 'var(--color-sage)', fontSize: 13 }
const navBtn: React.CSSProperties = { background: 'transparent', border: '1px solid var(--color-mist)', borderRadius: 8, padding: '4px 10px', fontSize: 16, cursor: 'pointer', lineHeight: 1 }
const dateInput: React.CSSProperties = { border: '1px solid var(--color-mist)', borderRadius: 10, padding: '9px 12px', fontSize: 14, background: 'var(--color-linen)' }
