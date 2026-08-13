import { useState } from 'react'
import { useSavingsGoals, useSavingsGoalMutations, type SavingsGoal } from '../hooks/useSavingsGoals'
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
import { CURRENCY_OPTS, type Currency } from '../lib/currencies'

const CUR_OPTS = CURRENCY_OPTS

function GoalModal({ open, onClose, onSubmit }: { open: boolean; onClose: () => void; onSubmit: (b: { name: string; target_amount: number; currency: string; deadline?: string | null }) => void }) {
  const [name, setName] = useState('')
  const [target, setTarget] = useState('')
  const [currency, setCurrency] = useState('USD')
  const [deadline, setDeadline] = useState('')
  const [error, setError] = useState('')
  function submit() {
    if (!name.trim()) { setError('Poné un nombre'); return }
    const t = parseAmount(target)
    if (isNaN(t) || t <= 0) { setError('Objetivo inválido'); return }
    onSubmit({ name: name.trim(), target_amount: t, currency, deadline: deadline || null })
  }
  return (
    <Modal open={open} onClose={onClose} title="Nueva meta">
      <div style={{ display: 'grid', gap: 12 }}>
        <input value={name} onChange={(e) => { setName(e.target.value); setError('') }} placeholder="Nombre (ej. Viaje)" style={inputStyle} />
        <label style={labelStyle}>Objetivo
          <input inputMode="decimal" value={target} onChange={(e) => { setTarget(e.target.value); setError('') }} placeholder="0" style={inputStyle} />
        </label>
        <Select value={currency} onValueChange={setCurrency} options={CUR_OPTS} ariaLabel="Moneda" style={{ width: '100%' }} />
        <label style={labelStyle}>Fecha límite (opcional)
          <input type="date" value={deadline} onChange={(e) => setDeadline(e.target.value)} style={inputStyle} />
        </label>
        {error && <span style={{ fontSize: 12, color: 'var(--color-error)' }}>{error}</span>}
        <button onClick={submit} style={ctaBtn}>Guardar</button>
      </div>
    </Modal>
  )
}

function AportarModal({ goal, onClose, onSubmit }: { goal: SavingsGoal | null; onClose: () => void; onSubmit: (id: number, current: number) => void }) {
  const [amount, setAmount] = useState('')
  const [error, setError] = useState('')
  if (!goal) return null
  function submit() {
    const a = parseAmount(amount)
    if (isNaN(a) || a <= 0) { setError('Monto inválido'); return }
    onSubmit(goal!.id, goal!.current_amount + a)
  }
  return (
    <Modal open={goal !== null} onClose={onClose} title={`Aportar a ${goal.name}`}>
      <div style={{ display: 'grid', gap: 12 }}>
        <label style={labelStyle}>Monto a aportar
          <input inputMode="decimal" value={amount} onChange={(e) => { setAmount(e.target.value); setError('') }} placeholder="0" style={inputStyle} />
        </label>
        {error && <span style={{ fontSize: 12, color: 'var(--color-error)' }}>{error}</span>}
        <span style={{ fontSize: 11, color: 'var(--color-sage)' }}>El aporte es un registro, no mueve plata de tus cuentas.</span>
        <button onClick={submit} style={ctaBtn}>Aportar</button>
      </div>
    </Modal>
  )
}

export default function Metas() {
  const { data, isLoading } = useSavingsGoals()
  const { create, update, remove } = useSavingsGoalMutations()
  const [createOpen, setCreateOpen] = useState(false)
  const [aportar, setAportar] = useState<SavingsGoal | null>(null)
  const [deleteGoal, setDeleteGoal] = useState<SavingsGoal | null>(null)

  if (isLoading) return <MovimientosSkeleton />
  const goals = data ?? []

  return (
    <div style={{ padding: '14px 18px 24px', display: 'grid', gap: 12 }}>
      <div style={{ display: 'flex', alignItems: 'center' }}>
        <BackButton />
        <div className="cap" style={{ flex: 1 }}>Metas de ahorro</div>
        <button onClick={() => setCreateOpen(true)} style={ghostBtn}>+ Nueva meta</button>
      </div>

      {goals.length === 0
        ? <EmptyState>Poné un objetivo — un viaje, un fondo de emergencia — y seguí tu avance.</EmptyState>
        : goals.map((g) => {
          const pct = g.target_amount > 0 ? Math.min(100, (g.current_amount / g.target_amount) * 100) : 0
          return (
            <Card key={g.id}>
              <div style={{ display: 'flex', alignItems: 'center' }}>
                <span style={{ fontSize: 15, fontWeight: 500, flex: 1 }}>{g.name}</span>
                <CardActions onEdit={() => setAportar(g)} onDelete={() => setDeleteGoal(g)} />
              </div>
              <div style={{ fontSize: 13, color: 'var(--color-sage)', marginTop: 4 }}>
                <Money value={g.current_amount} currency={g.currency as Currency} /> de <Money value={g.target_amount} currency={g.currency as Currency} /> ({Math.round(pct)}%)
                {g.deadline ? ` · hasta ${g.deadline}` : ''}
              </div>
              <div style={{ height: 8, borderRadius: 6, background: 'var(--color-mist)', overflow: 'hidden', marginTop: 8 }}>
                <div style={{ width: `${pct}%`, height: '100%', background: 'var(--color-voltage)' }} />
              </div>
              <button onClick={() => setAportar(g)} style={{ ...ghostBtn, marginTop: 10 }}>+ Aportar</button>
            </Card>
          )
        })}

      <GoalModal open={createOpen} onClose={() => setCreateOpen(false)} onSubmit={(b) => { create.mutate(b); setCreateOpen(false) }} />
      <AportarModal goal={aportar} onClose={() => setAportar(null)} onSubmit={(id, current) => { update.mutate({ id, current_amount: current }); setAportar(null) }} />
      <ConfirmDialog
        open={deleteGoal !== null}
        onOpenChange={(o) => { if (!o) setDeleteGoal(null) }}
        title="¿Borrar esta meta?"
        description={deleteGoal ? `Se eliminará "${deleteGoal.name}".` : ''}
        onConfirm={() => { if (deleteGoal) remove.mutate(deleteGoal.id); setDeleteGoal(null) }}
      />
      <div style={{ fontSize: 11, color: 'var(--color-sage)', textAlign: 'center' }}>
        Las metas son marcadores de avance — no mueven plata de tus cuentas.
      </div>
    </div>
  )
}

const ghostBtn: React.CSSProperties = { background: 'transparent', border: '1px solid var(--color-mist)', borderRadius: 10, padding: '7px 14px', fontSize: 13, cursor: 'pointer' }
const ctaBtn: React.CSSProperties = { background: 'var(--color-voltage)', color: 'var(--voltage-on-dark)', border: 'none', borderRadius: 10, padding: '14px', fontWeight: 500, cursor: 'pointer' }
const inputStyle: React.CSSProperties = { border: '1px solid var(--color-mist)', borderRadius: 10, padding: '10px 12px', fontSize: 14, background: 'var(--color-linen)', width: '100%', boxSizing: 'border-box' }
const labelStyle: React.CSSProperties = { display: 'grid', gap: 4, fontSize: 13, color: 'var(--color-sage)' }
