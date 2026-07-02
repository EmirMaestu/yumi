import { useState } from 'react'
import { useBudgets, useBudgetMutations, budgetPct, budgetColor, type Budget } from '../hooks/useBudgets'
import { useCategories } from '../hooks/useCategories'
import { parseAmount } from '../lib/parseAmount'
import { Money } from '../lib/privacy'
import Card from '../components/ui/Card'
import BackButton from '../components/ui/BackButton'
import EmptyState from '../components/ui/EmptyState'
import Modal from '../components/ui/Modal'
import ConfirmDialog from '../components/ui/ConfirmDialog'
import CardActions from '../components/ui/CardActions'
import Select from '../components/ui/Select'
import { MovimientosSkeleton } from '../components/ui/skeletons'

function BudgetModal({ open, onClose, initial, categoryOpts, onSubmit }: {
  open: boolean
  onClose: () => void
  initial?: Budget | null
  categoryOpts: { value: string; label: string }[]
  onSubmit: (categoryId: number, amount: number) => void
}) {
  const [categoryId, setCategoryId] = useState<string | undefined>(initial ? String(initial.category_id) : undefined)
  const [amount, setAmount] = useState(initial ? String(initial.amount) : '')
  const [error, setError] = useState('')
  const isEdit = !!initial

  function submit() {
    const cid = isEdit ? initial!.category_id : Number(categoryId)
    if (!cid) { setError('Elegí una categoría'); return }
    const monto = parseAmount(amount)
    if (isNaN(monto) || monto <= 0) { setError('Ingresá un monto válido'); return }
    onSubmit(cid, monto)
  }

  return (
    <Modal open={open} onClose={onClose} title={isEdit ? `Editar presupuesto` : 'Nuevo presupuesto'}>
      <div style={{ display: 'grid', gap: 12 }}>
        {isEdit
          ? <div style={{ fontSize: 14, fontWeight: 500 }}>{initial!.name}</div>
          : <Select value={categoryId} onValueChange={(v) => { setCategoryId(v); if (error) setError('') }} options={categoryOpts} placeholder="Categoría…" ariaLabel="Categoría" style={{ width: '100%' }} />}
        <label style={{ display: 'grid', gap: 4, fontSize: 13, color: 'var(--color-sage)' }}>
          Monto mensual
          <input inputMode="decimal" value={amount} onChange={(e) => { setAmount(e.target.value); if (error) setError('') }} placeholder="0" style={inputStyle} />
        </label>
        {error && <span style={{ fontSize: 12, color: 'var(--color-error)' }}>{error}</span>}
        <button onClick={submit} style={ctaBtn}>Guardar</button>
      </div>
    </Modal>
  )
}

export default function Presupuestos() {
  const { data, isLoading } = useBudgets()
  const categories = useCategories()
  const { upsert, remove } = useBudgetMutations()

  const [createOpen, setCreateOpen] = useState(false)
  const [editBudget, setEditBudget] = useState<Budget | null>(null)
  const [deleteBudget, setDeleteBudget] = useState<Budget | null>(null)

  if (isLoading) return <MovimientosSkeleton />

  const budgets = data ?? []
  const budgetedCatIds = new Set(budgets.map((b) => b.category_id))
  const categoryOpts = (categories.data ?? [])
    .filter((c) => !budgetedCatIds.has(c.id))
    .map((c) => ({ value: String(c.id), label: c.name }))

  return (
    <div style={{ padding: '14px 18px 24px', display: 'grid', gap: 12 }}>
      <div style={{ display: 'flex', alignItems: 'center' }}>
        <BackButton />
        <div className="cap" style={{ flex: 1 }}>Presupuestos</div>
        <button onClick={() => setCreateOpen(true)} style={ghostBtn}>+ Nuevo presupuesto</button>
      </div>

      {budgets.length === 0
        ? <EmptyState>Definí cuánto querés gastar por categoría y te avisamos si te pasás.</EmptyState>
        : budgets.map((b) => {
          const pct = budgetPct(b)
          const color = budgetColor(pct)
          return (
            <Card key={b.id}>
              <div style={{ display: 'flex', alignItems: 'center' }}>
                <span style={{ fontSize: 15, fontWeight: 500, flex: 1 }}>
                  {b.icon ? `${b.icon} ` : ''}{b.name}
                </span>
                <CardActions onEdit={() => setEditBudget(b)} onDelete={() => setDeleteBudget(b)} />
              </div>
              <div style={{ fontSize: 13, color: 'var(--color-sage)', marginTop: 4 }}>
                <Money value={b.spent} /> de <Money value={b.amount} /> ({Math.round(pct)}%)
              </div>
              <div style={{ height: 8, borderRadius: 6, background: 'var(--color-mist)', overflow: 'hidden', marginTop: 8 }}>
                <div style={{ width: `${Math.min(100, pct)}%`, height: '100%', background: color }} />
              </div>
            </Card>
          )
        })}

      <BudgetModal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        categoryOpts={categoryOpts}
        onSubmit={(cid, amount) => { upsert.mutate({ category_id: cid, amount }); setCreateOpen(false) }}
      />
      <BudgetModal
        key={editBudget ? `b-${editBudget.id}` : 'b-edit'}
        open={editBudget !== null}
        onClose={() => setEditBudget(null)}
        initial={editBudget}
        categoryOpts={categoryOpts}
        onSubmit={(cid, amount) => { upsert.mutate({ category_id: cid, amount }); setEditBudget(null) }}
      />
      <ConfirmDialog
        open={deleteBudget !== null}
        onOpenChange={(o) => { if (!o) setDeleteBudget(null) }}
        title="¿Borrar este presupuesto?"
        description={deleteBudget ? `Se eliminará el presupuesto de "${deleteBudget.name}".` : ''}
        onConfirm={() => { if (deleteBudget) remove.mutate(deleteBudget.id); setDeleteBudget(null) }}
      />
    </div>
  )
}

const ghostBtn: React.CSSProperties = { background: 'transparent', border: '1px solid var(--color-mist)', borderRadius: 10, padding: '7px 14px', fontSize: 13, cursor: 'pointer' }
const ctaBtn: React.CSSProperties = { background: 'var(--color-voltage)', color: 'var(--voltage-on-dark)', border: 'none', borderRadius: 10, padding: '14px', fontWeight: 500, cursor: 'pointer' }
const inputStyle: React.CSSProperties = { border: '1px solid var(--color-mist)', borderRadius: 10, padding: '10px 12px', fontSize: 14, background: 'var(--color-linen)', width: '100%', boxSizing: 'border-box' }
