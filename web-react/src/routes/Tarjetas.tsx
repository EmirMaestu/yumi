import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { useVencimientos } from '../hooks/useVencimientos'
import { useRecurring } from '../hooks/useRecurring'
import { useAccounts, useAccountMutations } from '../hooks/useAccounts'
import { formatMoney } from '../lib/format'
import { type Account, type CicloTotal } from '../lib/types'
import Card from '../components/ui/Card'
import AlertPill from '../components/ui/AlertPill'
import Skeleton from '../components/ui/Skeleton'
import EmptyState from '../components/ui/EmptyState'
import Modal from '../components/ui/Modal'
import ConfirmDialog from '../components/ui/ConfirmDialog'

function cicloTotal(arr?: CicloTotal[]): number { return (arr ?? []).reduce((s, c) => s + c.total, 0) }

interface CardForm { name: string; closing_day: number; due_day: number }

function EditCardModal({ open, onClose, card, onSubmit }: {
  open: boolean
  onClose: () => void
  card: Account | null
  onSubmit: (data: CardForm) => void
}) {
  const { register, handleSubmit, reset } = useForm<CardForm>({
    values: card ? { name: card.name, closing_day: card.closing_day ?? 1, due_day: card.due_day ?? 1 } : { name: '', closing_day: 1, due_day: 1 },
  })
  const submit = (data: CardForm) => { onSubmit(data); reset() }
  return (
    <Modal open={open} onClose={() => { onClose(); reset() }} title="Editar tarjeta">
      <form onSubmit={handleSubmit(submit)} style={{ display: 'grid', gap: 12 }}>
        <input
          {...register('name', { required: true })}
          placeholder="Nombre de la tarjeta"
          style={inputStyle}
        />
        <label style={labelStyle}>
          Día de cierre
          <input
            type="number"
            {...register('closing_day', { valueAsNumber: true, min: 1, max: 31 })}
            style={inputStyle}
          />
        </label>
        <label style={labelStyle}>
          Día de vencimiento
          <input
            type="number"
            {...register('due_day', { valueAsNumber: true, min: 1, max: 31 })}
            style={inputStyle}
          />
        </label>
        <button type="submit" style={ctaBtn}>Guardar</button>
      </form>
    </Modal>
  )
}

export default function Tarjetas() {
  const venc = useVencimientos()
  const recurring = useRecurring()
  const accounts = useAccounts()
  const { update, remove } = useAccountMutations()

  const [editCard, setEditCard] = useState<Account | null>(null)
  const [deleteCard, setDeleteCard] = useState<Account | null>(null)

  const cards = accounts.data?.filter((a) => a.type === 'credito') ?? []
  const cuotasByAccount = (id: number) =>
    (recurring.data ?? []).filter((r) => r.account_id === id && r.total_installments)

  if (accounts.isLoading) return <div style={{ padding: 18 }}><Skeleton h={120} /></div>
  if (cards.length === 0) return <EmptyState>No tenés tarjetas de crédito cargadas.</EmptyState>

  return (
    <div style={{ padding: '14px 18px 24px', display: 'grid', gap: 14 }}>
      <div className="cap">Tarjetas y cuotas</div>
      {cards.map((card) => {
        const v = venc.data?.find((x) => x.account_id === card.id)
        const cuotas = cuotasByAccount(card.id)
        const comprometido = cuotas.reduce((s, r) => s + r.amount * ((r.total_installments ?? 0) - (r.installments_fired ?? 0)), 0)
        const pagarMonto = cicloTotal(v?.ciclo_cerrado)
        return (
          <Card key={card.id}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <span style={{ fontSize: 16, fontWeight: 500 }}>{card.name}</span>
                <button aria-label={`Editar ${card.name}`} onClick={() => setEditCard(card)} style={iconBtn}>
                  <i className="ti ti-edit" aria-hidden />
                </button>
                <button aria-label={`Borrar ${card.name}`} onClick={() => setDeleteCard(card)} style={iconBtn}>
                  <i className="ti ti-trash" aria-hidden />
                </button>
              </div>
              {v?.next_due && <span style={{ fontSize: 12, color: 'var(--color-sage)' }}>vence {v.next_due.slice(8, 10)}/{v.next_due.slice(5, 7)}</span>}
            </div>
            <div style={{ marginTop: 12 }}>
              <div className="cap">Comprometido en cuotas</div>
              <div className="num-serif" style={{ fontSize: 30, marginTop: 4 }}>{formatMoney(comprometido)}</div>
            </div>
            {v && v.next_due && <div style={{ marginTop: 10 }}><AlertPill>pagar {formatMoney(pagarMonto)} el {v.next_due.slice(8, 10)}</AlertPill></div>}
            <div style={{ height: 1, background: 'var(--color-mist)', margin: '14px 0' }} />
            {cuotas.length === 0 ? <EmptyState>Sin cuotas activas.</EmptyState> : cuotas.map((r) => (
              <div key={r.id} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13, marginBottom: 8 }}>
                <span>{r.description} <span style={{ color: 'var(--color-sage)' }}>({(r.installments_fired ?? 0)}/{r.total_installments})</span></span>
                <span style={{ fontWeight: 500 }}>{formatMoney(r.amount, r.currency)}</span>
              </div>
            ))}
          </Card>
        )
      })}

      {/* Edit modal */}
      <EditCardModal
        open={editCard !== null}
        onClose={() => setEditCard(null)}
        card={editCard}
        onSubmit={(data) => {
          if (editCard) update.mutate({ id: editCard.id, name: data.name, closing_day: data.closing_day, due_day: data.due_day })
          setEditCard(null)
        }}
      />

      {/* Delete confirm */}
      <ConfirmDialog
        open={deleteCard !== null}
        onOpenChange={(o) => { if (!o) setDeleteCard(null) }}
        title="¿Borrar esta tarjeta?"
        description={deleteCard ? `Se eliminará "${deleteCard.name}".` : ''}
        onConfirm={() => {
          if (deleteCard) remove.mutate(deleteCard.id)
          setDeleteCard(null)
        }}
      />
    </div>
  )
}

const iconBtn: React.CSSProperties = { background: 'none', border: 'none', cursor: 'pointer', color: 'var(--color-sage)', fontSize: 16, padding: 2 }
const ctaBtn: React.CSSProperties = { background: 'var(--color-voltage)', color: 'var(--voltage-on-dark)', border: 'none', borderRadius: 10, padding: '14px', fontWeight: 500, cursor: 'pointer' }
const inputStyle: React.CSSProperties = { border: '1px solid var(--color-mist)', borderRadius: 10, padding: '10px 12px', fontSize: 14, background: 'var(--color-linen)', width: '100%', boxSizing: 'border-box' }
const labelStyle: React.CSSProperties = { display: 'grid', gap: 4, fontSize: 13, color: 'var(--color-sage)' }
