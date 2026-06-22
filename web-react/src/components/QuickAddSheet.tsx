import { type SubmitHandler, useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import Sheet from './ui/Sheet'
import { useAccounts } from '../hooks/useAccounts'
import { useCategories } from '../hooks/useCategories'
import { useTxMutations } from '../hooks/useTransactions'

const schema = z.object({
  type: z.enum(['gasto', 'ingreso']),
  amount: z.coerce.number().positive('Monto inválido'),
  description: z.string().min(1, 'Falta descripción'),
  account_id: z.coerce.number().int(),
  category_id: z.coerce.number().int().optional(),
})
type FormInput = z.input<typeof schema>
type FormOutput = z.output<typeof schema>

export default function QuickAddSheet({ onClose }: { onClose: () => void }) {
  const accounts = useAccounts()
  const categories = useCategories()
  const { create } = useTxMutations()
  const { register, handleSubmit, formState: { errors } } = useForm<FormInput, unknown, FormOutput>({
    resolver: zodResolver(schema), defaultValues: { type: 'gasto' },
  })

  const onSubmit: SubmitHandler<FormOutput> = (v) => create.mutate(v, { onSuccess: onClose })

  return (
    <Sheet title="Agregar gasto" onClose={onClose}>
      <form onSubmit={handleSubmit(onSubmit)} style={{ display: 'grid', gap: 12 }}>
        <select {...register('type')} style={field}><option value="gasto">Gasto</option><option value="ingreso">Ingreso</option></select>
        <input {...register('amount')} inputMode="decimal" placeholder="Monto" style={field} />
        {errors.amount && <small style={err}>{errors.amount.message}</small>}
        <input {...register('description')} placeholder="Descripción" style={field} />
        {errors.description && <small style={err}>{errors.description.message}</small>}
        <select {...register('account_id')} style={field}>
          <option value="">Cuenta…</option>
          {accounts.data?.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
        </select>
        <select {...register('category_id')} style={field}>
          <option value="">Categoría (opcional)…</option>
          {categories.data?.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
        <button type="submit" disabled={create.isPending} style={cta}>{create.isPending ? 'Guardando…' : 'Guardar →'}</button>
        <p style={{ fontSize: 12, color: 'var(--color-sage)', textAlign: 'center', margin: 0 }}>También podés mandarle un mensaje al bot.</p>
      </form>
    </Sheet>
  )
}

const field: React.CSSProperties = { border: '1px solid var(--color-mist)', borderRadius: 10, padding: '12px 14px', fontSize: 16, background: 'transparent' }
const cta: React.CSSProperties = { background: 'var(--color-voltage)', color: 'var(--voltage-on-dark)', border: 'none', borderRadius: 10, padding: '14px', fontWeight: 500, boxShadow: 'var(--shadow-cta)', cursor: 'pointer' }
const err: React.CSSProperties = { color: '#a32d2d', fontSize: 12 }
