import { useState } from 'react'
import * as Checkbox from '@radix-ui/react-checkbox'
import { useTransactions, useTxMutations } from '../hooks/useTransactions'
import { type TxFilters } from '../hooks/useTransactions'
import { useAccounts } from '../hooks/useAccounts'
import { useCategories } from '../hooks/useCategories'
import { formatMoney } from '../lib/format'
import { type Transaction } from '../lib/types'
import { MovimientosSkeleton } from '../components/ui/skeletons'
import EmptyState from '../components/ui/EmptyState'
import Select from '../components/ui/Select'
import Modal from '../components/ui/Modal'
import ConfirmDialog from '../components/ui/ConfirmDialog'
import EditTxModal from '../components/EditTxModal'

const PERIOD_OPTS = [
  { value: 'mes', label: 'Mes' },
  { value: 'mes pasado', label: 'Mes pasado' },
  { value: 'año', label: 'Año' },
  { value: 'todo', label: 'Todo' },
]

export default function Movimientos() {
  const [filters, setFilters] = useState<TxFilters>({ period: 'mes' })
  const { data, isLoading } = useTransactions(filters)
  const accounts = useAccounts()
  const categories = useCategories()
  const { remove, bulkDelete, bulkMove } = useTxMutations()

  // Selection
  const [selectMode, setSelectMode] = useState(false)
  const [sel, setSel] = useState<Set<number>>(new Set())
  const toggleSel = (id: number) => setSel((prev) => {
    const next = new Set(prev)
    if (next.has(id)) next.delete(id); else next.add(id)
    return next
  })

  // Modals
  const [moveOpen, setMoveOpen] = useState(false)
  const [moveAccountId, setMoveAccountId] = useState<string | undefined>(undefined)
  const [bulkDeleteOpen, setBulkDeleteOpen] = useState(false)

  // Per-row actions
  const [editTx, setEditTx] = useState<Transaction | null>(null)
  const [deleteTx, setDeleteTx] = useState<Transaction | null>(null)

  const accountOpts = [
    { value: 'all', label: 'Toda cuenta' },
    ...(accounts.data ?? []).map((a) => ({ value: String(a.id), label: a.name })),
  ]
  const categoryOpts = [
    { value: 'all', label: 'Toda categoría' },
    ...(categories.data ?? []).map((c) => ({ value: String(c.id), label: c.name })),
  ]
  const moveAccountOpts = (accounts.data ?? []).map((a) => ({ value: String(a.id), label: a.name }))

  return (
    <div style={{ padding: '14px 18px 24px' }}>
      <div style={{ display: 'flex', alignItems: 'center', marginBottom: 12 }}>
        <div className="cap" style={{ flex: 1 }}>Movimientos</div>
        {!selectMode
          ? <button onClick={() => setSelectMode(true)} style={selectModeBtn}>Seleccionar</button>
          : <button onClick={() => { setSelectMode(false); setSel(new Set()) }} style={selectModeBtn}>Cancelar</button>
        }
      </div>

      {/* Filters */}
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 16 }}>
        <Select
          value={filters.period ?? 'mes'}
          onValueChange={(v) => setFilters((f) => ({ ...f, period: v }))}
          options={PERIOD_OPTS}
          ariaLabel="Período"
        />
        <Select
          value={filters.account_id ? String(filters.account_id) : 'all'}
          onValueChange={(v) => setFilters((f) => ({ ...f, account_id: v === 'all' ? undefined : Number(v) }))}
          options={accountOpts}
          ariaLabel="Cuenta"
        />
        <Select
          value={filters.category_id ? String(filters.category_id) : 'all'}
          onValueChange={(v) => setFilters((f) => ({ ...f, category_id: v === 'all' ? undefined : Number(v) }))}
          options={categoryOpts}
          ariaLabel="Categoría"
        />
        <input
          placeholder="Buscar…"
          value={filters.q ?? ''}
          onChange={(e) => setFilters((f) => ({ ...f, q: e.target.value }))}
          style={{ border: '1px solid var(--color-mist)', borderRadius: 10, padding: '9px 12px', fontSize: 14, background: 'var(--color-linen)', flex: 1, minWidth: 120 }}
        />
      </div>

      {/* Selection toolbar */}
      {sel.size > 0 && (
        <div style={{ position: 'sticky', top: 0, zIndex: 20, display: 'flex', alignItems: 'center', gap: 10, padding: '10px 0', borderBottom: '1px solid var(--color-mist)', background: 'var(--color-linen)', marginBottom: 8 }}>
          <span style={{ fontSize: 14, fontWeight: 500, flex: 1 }}>{sel.size} seleccionado{sel.size === 1 ? '' : 's'}</span>
          <button onClick={() => setMoveOpen(true)} style={ghostBtn}>Mover</button>
          <button onClick={() => setBulkDeleteOpen(true)} style={ghostBtn}>Borrar</button>
          <button onClick={() => setSel(new Set())} aria-label="Limpiar selección" style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 18, color: 'var(--color-sage)' }}>×</button>
        </div>
      )}

      {isLoading && <MovimientosSkeleton />}
      {data && data.length === 0 && <EmptyState>Sin movimientos para este filtro.</EmptyState>}
      {data?.map((t) => (
        <div key={t.id} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '12px 0', borderBottom: '1px solid var(--color-mist)' }}>
          {/* Checkbox — only in selectMode */}
          {selectMode && (
            <Checkbox.Root
              checked={sel.has(t.id)}
              onCheckedChange={() => toggleSel(t.id)}
              aria-label={`Seleccionar ${t.description}`}
              style={{ width: 18, height: 18, border: '1px solid var(--color-mist)', borderRadius: 5, background: sel.has(t.id) ? 'var(--color-voltage)' : 'transparent', display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer', flexShrink: 0 }}
            >
              <Checkbox.Indicator>
                <i className="ti ti-check" style={{ fontSize: 13, color: 'var(--voltage-on-dark)' }} aria-hidden />
              </Checkbox.Indicator>
            </Checkbox.Root>
          )}

          {/* Content */}
          <span style={{ flex: 1, minWidth: 0 }}>
            <span style={{ fontSize: 14, fontWeight: 500 }}>{t.description}</span><br />
            <span style={{ fontSize: 11, color: 'var(--color-sage)' }}>{t.cat_name ?? 'sin categoría'} · {t.acc_name ?? ''} · {t.occurred_at.slice(0, 10)}</span>
          </span>

          {/* Amount + actions */}
          <span style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
            <span style={{ fontSize: 15, fontWeight: 500, color: t.type === 'ingreso' ? '#3b6d11' : 'var(--color-obsidian-ink)' }}>
              {t.type === 'ingreso' ? '+' : '−'}{formatMoney(t.amount, t.currency)}
            </span>
            <button aria-label={`Editar ${t.description}`} onClick={() => setEditTx(t)} style={iconBtn}>
              <i className="ti ti-edit" aria-hidden />
            </button>
            <button aria-label={`Borrar ${t.description}`} onClick={() => setDeleteTx(t)} style={iconBtn}>
              <i className="ti ti-trash" aria-hidden />
            </button>
          </span>
        </div>
      ))}

      {/* Bulk move modal */}
      <Modal open={moveOpen} onClose={() => setMoveOpen(false)} title="Mover a cuenta">
        <div style={{ display: 'grid', gap: 12 }}>
          <Select
            value={moveAccountId}
            onValueChange={setMoveAccountId}
            options={moveAccountOpts}
            placeholder="Seleccionar cuenta…"
            ariaLabel="Cuenta destino"
            style={{ width: '100%' }}
          />
          <button
            onClick={() => {
              if (!moveAccountId) return
              bulkMove.mutate({ ids: [...sel], account_id: Number(moveAccountId) })
              setSel(new Set())
              setMoveOpen(false)
            }}
            style={ctaBtn}
          >
            Mover {sel.size} movimiento{sel.size === 1 ? '' : 's'} →
          </button>
        </div>
      </Modal>

      {/* Bulk delete confirm */}
      <ConfirmDialog
        open={bulkDeleteOpen}
        onOpenChange={setBulkDeleteOpen}
        title={`¿Borrar ${sel.size} gasto${sel.size === 1 ? '' : 's'}?`}
        description="Esta acción no se puede deshacer."
        onConfirm={() => {
          bulkDelete.mutate([...sel])
          setSel(new Set())
          setBulkDeleteOpen(false)
        }}
      />

      {/* Per-row edit modal */}
      <EditTxModal
        key={editTx ? `tx-${editTx.id}` : 'tx-edit'}
        tx={editTx}
        open={editTx !== null}
        onClose={() => setEditTx(null)}
      />

      {/* Per-row delete confirm */}
      <ConfirmDialog
        open={deleteTx !== null}
        onOpenChange={(o) => { if (!o) setDeleteTx(null) }}
        title="¿Borrar este gasto?"
        description={deleteTx ? `Se eliminará "${deleteTx.description}".` : ''}
        onConfirm={() => {
          if (deleteTx) remove.mutate(deleteTx.id)
          setDeleteTx(null)
        }}
      />
    </div>
  )
}

const iconBtn: React.CSSProperties = { background: 'none', border: 'none', cursor: 'pointer', color: 'var(--color-sage)', fontSize: 16, padding: 2 }
const ghostBtn: React.CSSProperties = { background: 'transparent', border: '1px solid var(--color-mist)', borderRadius: 10, padding: '7px 14px', fontSize: 13, cursor: 'pointer' }
const ctaBtn: React.CSSProperties = { background: 'var(--color-voltage)', color: 'var(--voltage-on-dark)', border: 'none', borderRadius: 10, padding: '14px', fontWeight: 500, cursor: 'pointer' }
const selectModeBtn: React.CSSProperties = { background: 'transparent', border: 'none', cursor: 'pointer', color: 'var(--color-sage)', fontSize: 13 }
