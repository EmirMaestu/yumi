import { useMemo, useRef, useState, type CSSProperties } from 'react'
import { useSearchParams } from 'react-router-dom'
import * as Checkbox from '@radix-ui/react-checkbox'
import { useTransactionsInfinite, useTxMutations, type TxFilters } from '../hooks/useTransactions'
import { useAccounts } from '../hooks/useAccounts'
import { useCategories } from '../hooks/useCategories'
import { formatMonthLabel, formatDayHeader } from '../lib/format'
import { Money } from '../lib/privacy'
import { type Transaction } from '../lib/types'
import { MovimientosSkeleton } from '../components/ui/skeletons'
import BackButton from '../components/ui/BackButton'
import Select from '../components/ui/Select'
import Sheet from '../components/ui/Sheet'
import Modal from '../components/ui/Modal'
import ConfirmDialog from '../components/ui/ConfirmDialog'
import EditTxModal from '../components/EditTxModal'
import TxDetailSheet from '../components/TxDetailSheet'

type Period =
  | { mode: 'month'; year: number; month: number }
  | { mode: 'year'; year: number }
  | { mode: 'all' }
  | { mode: 'range'; from: string; to: string }
type TypeFilter = 'gasto' | 'ingreso' | undefined

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
  const [type, setType] = useState<TypeFilter>(sp.get('type') === 'ingreso' ? 'ingreso' : sp.get('type') === 'gasto' ? 'gasto' : undefined)
  const [filtersOpen, setFiltersOpen] = useState(false)

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
  const sumBy = (t: 'gasto' | 'ingreso') =>
    sums.filter((s) => s.kind === 'normal' && s.type === t && s.currency === 'ARS').reduce((a, s) => a + s.total, 0)
  const totalGastos = sumBy('gasto')
  const totalIngresos = sumBy('ingreso')

  // Deshacer inline: ocultamos la fila y confirmamos el borrado tras unos segundos.
  const [pendingUndo, setPendingUndo] = useState<{ id: number; label: string } | null>(null)
  const undoTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const softDelete = (t: Transaction) => {
    if (undoTimer.current) { clearTimeout(undoTimer.current); if (pendingUndo) remove.mutate(pendingUndo.id) }
    setPendingUndo({ id: t.id, label: t.description })
    undoTimer.current = setTimeout(() => { remove.mutate(t.id); setPendingUndo(null); undoTimer.current = null }, 5000)
  }
  const undoDelete = () => {
    if (undoTimer.current) { clearTimeout(undoTimer.current); undoTimer.current = null }
    setPendingUndo(null)
  }

  // Agrupación por día, preservando el orden desc.
  const visibleItems = useMemo(() => items.filter((t) => t.id !== pendingUndo?.id), [items, pendingUndo])
  const groups = useMemo(() => {
    const map: { day: string; items: Transaction[] }[] = []
    for (const t of visibleItems) {
      const day = t.occurred_at.slice(0, 10)
      const last = map[map.length - 1]
      if (last && last.day === day) last.items.push(t)
      else map.push({ day, items: [t] })
    }
    return map
  }, [visibleItems])
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

  const moveAccountOpts = (accounts.data ?? []).map((a) => ({ value: String(a.id), label: a.name }))
  const activeFilterCount = (type ? 1 : 0) + (account_id ? 1 : 0) + (category_id ? 1 : 0)
  const clearFilters = () => { setType(undefined); setAccountId(undefined); setCategoryId(undefined) }

  // Navegador de mes (fijo arriba).
  const now = new Date()
  const atCurrentMonth = period.mode === 'month' && period.year === now.getFullYear() && period.month === now.getMonth() + 1
  const stepMonth = (delta: number) => setPeriod((p) => {
    if (p.mode !== 'month') return currentMonth()
    const d = new Date(p.year, p.month - 1 + delta, 1)
    return { mode: 'month', year: d.getFullYear(), month: d.getMonth() + 1 }
  })
  const monthLabel = period.mode === 'month'
    ? formatMonthLabel(period.year, period.month)
    : period.mode === 'year' ? String(period.year) : period.mode === 'all' ? 'Todo' : 'Rango'

  // Export CSV
  const exportHref = period.mode === 'month'
    ? `/api/export.csv?year=${period.year}&month=${period.month}`
    : '/api/export.csv'

  return (
    <div style={{ padding: '14px 18px 24px' }}>
      <div style={{ display: 'flex', alignItems: 'center', marginBottom: 4 }}>
        <BackButton />
        <div className="num-serif" style={{ flex: 1, fontSize: 26 }}>Movimientos</div>
        <button onClick={() => setFiltersOpen(true)} style={filtersPill}>
          Filtros{activeFilterCount > 0 ? ` · ${activeFilterCount}` : ''}
        </button>
      </div>

      {/* Navegador de mes fijo */}
      <div style={monthNav}>
        <button onClick={() => stepMonth(-1)} aria-label="Mes anterior" style={monthArrow}>‹</button>
        <span style={{ fontSize: 14, fontWeight: 500, textTransform: 'capitalize' }}>{monthLabel} {period.mode === 'month' ? period.year : ''}</span>
        <button onClick={() => stepMonth(1)} disabled={atCurrentMonth} aria-label="Mes siguiente" style={{ ...monthArrow, opacity: atCurrentMonth ? 0.35 : 1 }}>›</button>
      </div>

      {/* Totales del filtro aplicado */}
      <div style={{ display: 'flex', gap: 20, margin: '12px 2px 0' }}>
        <div>
          <div className="cap" style={{ fontSize: 9.5 }}>Salidas</div>
          <div className="num-serif" style={{ fontSize: 16, marginTop: 2 }}><Money value={totalGastos} /></div>
        </div>
        <div>
          <div className="cap" style={{ fontSize: 9.5 }}>Entradas</div>
          <div className="num-serif" style={{ fontSize: 16, marginTop: 2, color: '#3b6d11' }}><Money value={totalIngresos} /></div>
        </div>
        <div style={{ marginLeft: 'auto', alignSelf: 'flex-end' }}>
          <a href={exportHref} download style={{ ...ghostBtn, textDecoration: 'none', display: 'inline-flex', alignItems: 'center', gap: 4, marginRight: 6 }}>
            <i className="ti ti-download" aria-hidden /> Exportar
          </a>
          {!selectMode
            ? <button onClick={() => setSelectMode(true)} style={ghostBtn}>Seleccionar</button>
            : <button onClick={() => { setSelectMode(false); setSel(new Set()) }} style={ghostBtn}>Cancelar</button>}
        </div>
      </div>

      {/* Búsqueda */}
      <div style={searchBox}>
        <i className="ti ti-search" aria-hidden style={{ color: 'var(--color-sage)' }} />
        <input placeholder="Buscar descripción, monto…" value={q} onChange={(e) => setQ(e.target.value)}
          style={{ border: 'none', background: 'transparent', outline: 'none', fontSize: 14, flex: 1, color: 'inherit' }} />
      </div>

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
      {!isLoading && visibleItems.length === 0 && !pendingUndo && (
        <div style={{ textAlign: 'center', padding: '40px 18px', color: 'var(--color-sage)' }}>
          <div style={{ fontSize: 15, fontWeight: 500, color: 'var(--color-obsidian-ink)' }}>Sin movimientos para este filtro</div>
          <div style={{ fontSize: 13, marginTop: 6 }}>Cargá un gasto desde el botón + o escribile al bot.</div>
        </div>
      )}

      {/* Deshacer inline */}
      {pendingUndo && (
        <div style={undoBar}>
          <span style={{ fontSize: 12.5, color: 'var(--color-sage)', flex: 1 }}>Movimiento borrado</span>
          <button onClick={undoDelete} style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 12.5, fontWeight: 600, color: '#3b6d11', font: 'inherit' }}>Deshacer</button>
        </div>
      )}

      {groups.map((g) => (
        <div key={g.day}>
          <div style={{ position: 'sticky', top: 0, zIndex: 5, display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', background: 'var(--color-linen)', padding: '10px 0 4px' }}>
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
                  <button aria-label={`Borrar ${t.description}`} onClick={() => softDelete(t)} style={iconBtn}><i className="ti ti-trash" aria-hidden /></button>
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

      {/* Drawer de filtros */}
      <Sheet open={filtersOpen} onClose={() => setFiltersOpen(false)} title="Filtros">
        <div style={{ display: 'grid', gap: 4 }}>
          <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
            <button onClick={clearFilters} style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 12.5, color: 'var(--color-sage)', font: 'inherit' }}>Limpiar</button>
          </div>

          <div className="cap" style={{ fontSize: 10, marginTop: 6 }}>Tipo</div>
          <div style={chipRow}>
            <FilterChip active={!type} onClick={() => setType(undefined)}>Todos</FilterChip>
            <FilterChip active={type === 'gasto'} onClick={() => setType('gasto')}>Gastos</FilterChip>
            <FilterChip active={type === 'ingreso'} onClick={() => setType('ingreso')}>Ingresos</FilterChip>
          </div>

          <div className="cap" style={{ fontSize: 10, marginTop: 14 }}>Cuenta</div>
          <div style={chipRow}>
            <FilterChip active={!account_id} onClick={() => setAccountId(undefined)}>Todas</FilterChip>
            {(accounts.data ?? []).map((a) => (
              <FilterChip key={a.id} active={account_id === a.id} onClick={() => setAccountId(account_id === a.id ? undefined : a.id)}>{a.name}</FilterChip>
            ))}
          </div>

          <div className="cap" style={{ fontSize: 10, marginTop: 14 }}>Categoría</div>
          <div style={chipRow}>
            <FilterChip active={!category_id} onClick={() => setCategoryId(undefined)}>Todas</FilterChip>
            {(categories.data ?? []).map((c) => (
              <FilterChip key={c.id} active={category_id === c.id} onClick={() => setCategoryId(category_id === c.id ? undefined : c.id)}>{c.icon ? `${c.icon} ` : ''}{c.name}</FilterChip>
            ))}
          </div>

          <button onClick={() => setFiltersOpen(false)} style={{ ...ctaBtn, marginTop: 20 }}>Ver {total} movimiento{total === 1 ? '' : 's'}</button>
        </div>
      </Sheet>

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

function FilterChip({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return <button onClick={onClick} style={active ? chipOn : chipOff}>{children}</button>
}

const iconBtn: CSSProperties = { background: 'none', border: 'none', cursor: 'pointer', color: 'var(--color-sage)', fontSize: 16, padding: 2 }
const ghostBtn: CSSProperties = { background: 'transparent', border: '1px solid var(--color-mist)', borderRadius: 10, padding: '7px 14px', fontSize: 13, cursor: 'pointer', color: 'inherit' }
const ctaBtn: CSSProperties = { background: 'var(--color-voltage)', color: 'var(--voltage-on-dark)', border: 'none', borderRadius: 12, padding: '14px', fontWeight: 600, fontSize: 14, cursor: 'pointer' }
const filtersPill: CSSProperties = { background: 'rgba(43,238,75,0.14)', color: 'var(--color-voltage-ink, #1f7a2e)', border: 'none', borderRadius: 9999, padding: '6px 12px', fontSize: 12, fontWeight: 600, cursor: 'pointer', font: 'inherit' }
const monthNav: CSSProperties = { display: 'flex', alignItems: 'center', justifyContent: 'space-between', background: 'var(--color-linen)', border: '1px solid var(--color-mist)', borderRadius: 12, padding: '9px 14px', marginTop: 12 }
const monthArrow: CSSProperties = { background: 'transparent', border: 'none', fontSize: 18, cursor: 'pointer', color: 'var(--color-sage)', lineHeight: 1, padding: '0 6px' }
const searchBox: CSSProperties = { display: 'flex', alignItems: 'center', gap: 9, border: '1px solid var(--color-mist)', borderRadius: 12, padding: '11px 13px', marginTop: 14, marginBottom: 8, background: 'var(--color-linen)' }
const undoBar: CSSProperties = { display: 'flex', alignItems: 'center', gap: 12, padding: '11px 14px', margin: '8px 0', borderRadius: 12, background: 'rgba(43,238,75,0.10)' }
const chipRow: CSSProperties = { display: 'flex', gap: 7, flexWrap: 'wrap', marginTop: 8 }
const chipBase: CSSProperties = { borderRadius: 9999, padding: '7px 13px', fontSize: 12, fontWeight: 600, cursor: 'pointer', font: 'inherit' }
const chipOff: CSSProperties = { ...chipBase, background: 'transparent', border: '1px solid var(--color-mist)', color: 'var(--color-obsidian-ink)' }
const chipOn: CSSProperties = { ...chipBase, background: 'var(--color-voltage)', border: '1px solid var(--color-voltage)', color: 'var(--voltage-on-dark)' }
