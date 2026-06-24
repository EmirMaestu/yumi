import { useEffect, useState } from 'react'
import { useForm, Controller } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useRecurring, useRecurringMutations } from '../hooks/useRecurring'
import { useAccounts } from '../hooks/useAccounts'
import { formatMoney } from '../lib/format'
import { type Recurring } from '../lib/types'
import Card from '../components/ui/Card'
import Modal from '../components/ui/Modal'
import ConfirmDialog from '../components/ui/ConfirmDialog'
import CardActions from '../components/ui/CardActions'
import EmptyState from '../components/ui/EmptyState'
import Select from '../components/ui/Select'
import { MovimientosSkeleton } from '../components/ui/skeletons'

// ---- Form schema ----
const schema = z.object({
  description: z.string().min(1, 'Requerido'),
  amount: z.number().positive('Debe ser mayor a 0'),
  account_id: z.string().min(1, 'Requerido'),
  type: z.enum(['gasto', 'ingreso']),
  day_of_month: z.number().min(1).max(31),
  total_installments: z.number().int().min(1).optional().nullable(),
  installments_fired: z.number().int().min(0).optional().nullable(),
})

type FormValues = z.infer<typeof schema>

const TYPE_OPTS = [
  { value: 'gasto', label: 'Gasto' },
  { value: 'ingreso', label: 'Ingreso' },
]

function RecurrenteModal({
  open,
  onClose,
  initial,
  title,
  onSubmit,
  accountOpts,
}: {
  open: boolean
  onClose: () => void
  initial?: Partial<FormValues>
  title: string
  onSubmit: (data: FormValues) => void
  accountOpts: { value: string; label: string }[]
}) {
  const { register, handleSubmit, control, reset, formState: { errors } } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      description: '',
      amount: undefined,
      account_id: '',
      type: 'gasto',
      day_of_month: 1,
      total_installments: null,
      installments_fired: null,
      ...initial,
    },
  })

  useEffect(() => {
    if (open) {
      reset({
        description: '',
        amount: undefined,
        account_id: '',
        type: 'gasto',
        day_of_month: 1,
        total_installments: null,
        installments_fired: null,
        ...initial,
      })
    }
  }, [open, reset]) // eslint-disable-line react-hooks/exhaustive-deps

  const submit = (data: FormValues) => {
    onSubmit(data)
    reset()
  }

  return (
    <Modal open={open} onClose={() => { onClose(); reset() }} title={title}>
      <form onSubmit={handleSubmit(submit)} style={{ display: 'grid', gap: 12 }}>
        <div>
          <input
            {...register('description')}
            placeholder="Descripción"
            style={inputStyle}
          />
          {errors.description && <span style={errorStyle}>{errors.description.message}</span>}
        </div>

        <label style={labelStyle}>
          Monto
          <input
            type="number"
            step="0.01"
            {...register('amount', { valueAsNumber: true })}
            style={inputStyle}
          />
          {errors.amount && <span style={errorStyle}>{errors.amount.message}</span>}
        </label>

        <Controller
          name="account_id"
          control={control}
          render={({ field }) => (
            <Select
              value={field.value}
              onValueChange={(v) => field.onChange(v)}
              options={accountOpts}
              placeholder="Cuenta"
              ariaLabel="Cuenta"
              style={{ width: '100%' }}
            />
          )}
        />
        {errors.account_id && <span style={errorStyle}>{errors.account_id.message}</span>}

        <Controller
          name="type"
          control={control}
          render={({ field }) => (
            <Select
              value={field.value}
              onValueChange={(v) => field.onChange(v)}
              options={TYPE_OPTS}
              ariaLabel="Tipo"
              style={{ width: '100%' }}
            />
          )}
        />

        <label style={labelStyle}>
          Día del mes
          <input
            type="number"
            min={1}
            max={31}
            {...register('day_of_month', { valueAsNumber: true })}
            style={inputStyle}
          />
          {errors.day_of_month && <span style={errorStyle}>{errors.day_of_month.message}</span>}
        </label>

        <label style={labelStyle}>
          Total de cuotas (opcional)
          <input
            type="number"
            min={1}
            placeholder="Dejar vacío si es fijo mensual"
            {...register('total_installments', { valueAsNumber: true, setValueAs: (v) => (v === '' || isNaN(v) ? null : Number(v)) })}
            style={inputStyle}
          />
        </label>

        <label style={labelStyle}>
          Cuotas ya pagadas (opcional)
          <input
            type="number"
            min={0}
            placeholder="0"
            {...register('installments_fired', { valueAsNumber: true, setValueAs: (v) => (v === '' || isNaN(v) ? null : Number(v)) })}
            style={inputStyle}
          />
        </label>

        <button type="submit" style={ctaBtn}>Guardar</button>
      </form>
    </Modal>
  )
}

export default function Recurrentes() {
  const recurring = useRecurring(true)
  const accounts = useAccounts()
  const { create, update, remove } = useRecurringMutations()

  const [newOpen, setNewOpen] = useState(false)
  const [editItem, setEditItem] = useState<Recurring | null>(null)
  const [deleteItem, setDeleteItem] = useState<Recurring | null>(null)

  const accountOpts = (accounts.data ?? []).map((a) => ({ value: String(a.id), label: a.name }))
  const accountName = (id: number) => accounts.data?.find((a) => a.id === id)?.name ?? String(id)

  const fmtDate = (dateStr?: string) =>
    dateStr ? `${dateStr.slice(8, 10)}/${dateStr.slice(5, 7)}` : '—'

  const handleCreate = (data: FormValues) => {
    create.mutate({
      description: data.description,
      amount: data.amount,
      account_id: Number(data.account_id),
      day_of_month: data.day_of_month,
      total_installments: data.total_installments ?? null,
      installments_fired: data.installments_fired ?? null,
    })
    setNewOpen(false)
  }

  const handleEdit = (data: FormValues) => {
    if (!editItem) return
    update.mutate({
      id: editItem.id,
      description: data.description,
      amount: data.amount,
      day_of_month: data.day_of_month,
      total_installments: data.total_installments ?? null,
      installments_fired: data.installments_fired ?? null,
    })
    setEditItem(null)
  }

  if (recurring.isLoading) return <MovimientosSkeleton />

  const items = recurring.data ?? []

  return (
    <div style={{ padding: '14px 18px 24px', display: 'grid', gap: 14 }}>
      {/* Page header */}
      <div style={{ display: 'flex', alignItems: 'center' }}>
        <div className="cap" style={{ flex: 1 }}>Recurrentes y cuotas</div>
        <button onClick={() => setNewOpen(true)} style={ghostBtn}>+ Nuevo</button>
      </div>

      {items.length === 0
        ? <EmptyState>No hay recurrentes cargados.</EmptyState>
        : items.map((r) => {
          const isPaused = r.active === 0
          const tag = r.total_installments
            ? `cuota ${r.installments_fired ?? 0}/${r.total_installments} · ${formatMoney(r.amount, r.currency)} c/u`
            : `fijo mensual · ${formatMoney(r.amount, r.currency)}`
          return (
            <Card key={r.id} style={{ opacity: isPaused ? 0.55 : 1 }}>
              <div style={{ display: 'flex', alignItems: 'flex-start' }}>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 15, fontWeight: 500 }}>{r.description}</div>
                  <div style={{ fontSize: 12, color: 'var(--color-sage)', marginTop: 2 }}>{accountName(r.account_id)}</div>
                  <div style={{ fontSize: 12, color: 'var(--color-sage)', marginTop: 3 }}>{tag}</div>
                  <div style={{ fontSize: 11, color: 'var(--color-sage)', marginTop: 4, display: 'flex', gap: 10 }}>
                    <span>próxima: {fmtDate(r.next_occurrence)}</span>
                    <span style={{ opacity: 0.7 }}>{r.total_installments ? 'cuota' : 'fijo'}</span>
                  </div>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexShrink: 0 }}>
                  <button
                    onClick={() => update.mutate({ id: r.id, active: isPaused ? 1 : 0 })}
                    style={pauseBtn}
                  >
                    {isPaused ? 'Reactivar' : 'Pausar'}
                  </button>
                  <CardActions
                    onEdit={() => setEditItem(r)}
                    onDelete={() => setDeleteItem(r)}
                  />
                </div>
              </div>
            </Card>
          )
        })
      }

      {/* New modal */}
      <RecurrenteModal
        open={newOpen}
        onClose={() => setNewOpen(false)}
        title="Nuevo recurrente"
        onSubmit={handleCreate}
        accountOpts={accountOpts}
      />

      {/* Edit modal */}
      <RecurrenteModal
        key={editItem ? `rec-${editItem.id}` : 'rec-edit'}
        open={editItem !== null}
        onClose={() => setEditItem(null)}
        title="Editar recurrente"
        initial={editItem ? {
          description: editItem.description,
          amount: editItem.amount,
          account_id: String(editItem.account_id),
          type: 'gasto',
          day_of_month: 1,
          total_installments: editItem.total_installments ?? null,
          installments_fired: editItem.installments_fired ?? null,
        } : undefined}
        onSubmit={handleEdit}
        accountOpts={accountOpts}
      />

      {/* Delete confirm */}
      <ConfirmDialog
        open={deleteItem !== null}
        onOpenChange={(o) => { if (!o) setDeleteItem(null) }}
        title="¿Borrar este recurrente?"
        description={deleteItem ? `Se eliminará "${deleteItem.description}".` : ''}
        onConfirm={() => {
          if (deleteItem) remove.mutate(deleteItem.id)
          setDeleteItem(null)
        }}
      />
    </div>
  )
}

const inputStyle: React.CSSProperties = {
  border: '1px solid var(--color-mist)',
  borderRadius: 10,
  padding: '10px 12px',
  fontSize: 14,
  background: 'var(--color-linen)',
  width: '100%',
  boxSizing: 'border-box',
}
const labelStyle: React.CSSProperties = { display: 'grid', gap: 4, fontSize: 13, color: 'var(--color-sage)' }
const errorStyle: React.CSSProperties = { fontSize: 12, color: '#c0392b', marginTop: 2 }
const ctaBtn: React.CSSProperties = {
  background: 'var(--color-voltage)',
  color: 'var(--voltage-on-dark)',
  border: 'none',
  borderRadius: 10,
  padding: '14px',
  fontWeight: 500,
  cursor: 'pointer',
}
const ghostBtn: React.CSSProperties = {
  background: 'transparent',
  border: '1px solid var(--color-mist)',
  borderRadius: 10,
  padding: '7px 14px',
  fontSize: 13,
  cursor: 'pointer',
}
const pauseBtn: React.CSSProperties = {
  background: 'transparent',
  border: '1px solid var(--color-mist)',
  borderRadius: 8,
  padding: '3px 10px',
  fontSize: 12,
  cursor: 'pointer',
  color: 'var(--color-sage)',
}
