import { type SubmitHandler, useForm, Controller } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import Modal from './ui/Modal'
import Select from './ui/Select'
import { useAccounts } from '../hooks/useAccounts'
import { useCategories } from '../hooks/useCategories'
import { useTxMutations } from '../hooks/useTransactions'
import { type Transaction } from '../lib/types'

const schema = z.object({
  type: z.enum(['gasto', 'ingreso']),
  amount: z.coerce.number().positive('Monto inválido'),
  description: z.string().min(1, 'Falta descripción'),
  account_id: z.coerce.number().int(),
  category_id: z.coerce.number().int().optional(),
})
type FormInput = z.input<typeof schema>
type FormOutput = z.output<typeof schema>

const tipoOpts = [
  { value: 'gasto', label: 'Gasto' },
  { value: 'ingreso', label: 'Ingreso' },
]

export default function EditTxModal({ tx, open, onClose }: { tx: Transaction | null; open: boolean; onClose: () => void }) {
  const accounts = useAccounts()
  const categories = useCategories()
  const { update } = useTxMutations()

  const { register, handleSubmit, control, formState: { errors } } = useForm<FormInput, unknown, FormOutput>({
    resolver: zodResolver(schema),
    values: tx ? {
      type: tx.type,
      amount: String(tx.amount),
      description: tx.description,
      account_id: String(tx.account_id),
      category_id: tx.category_id ? String(tx.category_id) : undefined,
    } : undefined,
  })

  const accountOpts = (accounts.data ?? []).map((a) => ({ value: String(a.id), label: a.name }))
  const categoryOpts = (categories.data ?? []).map((c) => ({ value: String(c.id), label: c.name }))

  const onSubmit: SubmitHandler<FormOutput> = (v) => {
    if (!tx) return
    update.mutate({ id: tx.id, ...v }, { onSuccess: onClose })
  }

  return (
    <Modal open={open} onClose={onClose} title="Editar movimiento">
      <form onSubmit={handleSubmit(onSubmit)} style={{ display: 'grid', gap: 12 }}>
        <Controller
          name="type"
          control={control}
          render={({ field }) => (
            <Select
              value={field.value}
              onValueChange={(v) => field.onChange(v)}
              options={tipoOpts}
              placeholder="Tipo…"
              ariaLabel="Tipo"
              style={{ width: '100%' }}
            />
          )}
        />
        <input {...register('amount')} inputMode="decimal" placeholder="Monto" style={fieldStyle} />
        {errors.amount && <small style={errStyle}>{errors.amount.message}</small>}
        <input {...register('description')} placeholder="Descripción" style={fieldStyle} />
        {errors.description && <small style={errStyle}>{errors.description.message}</small>}
        <Controller
          name="account_id"
          control={control}
          render={({ field }) => (
            <Select
              value={field.value ? String(field.value) : undefined}
              onValueChange={(v) => field.onChange(Number(v))}
              options={accountOpts}
              placeholder="Cuenta…"
              ariaLabel="Cuenta"
              style={{ width: '100%' }}
            />
          )}
        />
        <Controller
          name="category_id"
          control={control}
          render={({ field }) => (
            <Select
              value={field.value ? String(field.value) : undefined}
              onValueChange={(v) => field.onChange(Number(v))}
              options={categoryOpts}
              placeholder="Categoría (opcional)…"
              ariaLabel="Categoría"
              style={{ width: '100%' }}
            />
          )}
        />
        <button type="submit" disabled={update.isPending} style={ctaStyle}>{update.isPending ? 'Guardando…' : 'Guardar cambios →'}</button>
      </form>
    </Modal>
  )
}

const fieldStyle: React.CSSProperties = { border: '1px solid var(--color-mist)', borderRadius: 10, padding: '12px 14px', fontSize: 16, background: 'transparent' }
const ctaStyle: React.CSSProperties = { background: 'var(--color-voltage)', color: 'var(--voltage-on-dark)', border: 'none', borderRadius: 10, padding: '14px', fontWeight: 500, boxShadow: 'var(--shadow-cta)', cursor: 'pointer' }
const errStyle: React.CSSProperties = { color: '#a32d2d', fontSize: 12 }
