import { useEffect } from 'react'
import { useForm, Controller } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useAccountMutations } from '../hooks/useAccounts'
import { type Account } from '../lib/types'
import Modal from './ui/Modal'
import Select from './ui/Select'

const schema = z.object({
  name: z.string().min(1, 'Requerido'),
  type: z.enum(['efectivo', 'billetera', 'debito', 'credito', 'banco', 'dolares', 'cripto', 'inversion']),
  closing_day: z.number().min(1, 'Entre 1 y 31').max(31, 'Entre 1 y 31').optional(),
  due_day: z.number().min(1, 'Entre 1 y 31').max(31, 'Entre 1 y 31').optional(),
})

type FormValues = z.infer<typeof schema>

const TYPE_OPTS = [
  { value: 'efectivo', label: 'Efectivo' },
  { value: 'billetera', label: 'Billetera' },
  { value: 'debito', label: 'Débito' },
  { value: 'credito', label: 'Crédito' },
  { value: 'banco', label: 'Banco' },
  { value: 'dolares', label: 'Dólares (USD)' },
  { value: 'cripto', label: 'Cripto' },
  { value: 'inversion', label: 'Inversión' },
]

export default function AccountForm({
  account,
  open,
  onClose,
  defaultType,
}: {
  account?: Account | null
  open: boolean
  onClose: () => void
  defaultType?: Account['type']
}) {
  const { create, update } = useAccountMutations()
  const isEdit = !!account

  const { register, handleSubmit, control, watch, reset, formState: { errors } } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      name: '',
      type: defaultType ?? 'banco',
      closing_day: 1,
      due_day: 1,
    },
  })

  useEffect(() => {
    if (open) {
      reset(
        account
          ? {
              name: account.name,
              type: account.type,
              closing_day: account.closing_day ?? 1,
              due_day: account.due_day ?? 1,
            }
          : {
              name: '',
              type: defaultType ?? 'banco',
              closing_day: 1,
              due_day: 1,
            }
      )
    }
  }, [open, account, defaultType, reset])

  const watchedType = watch('type')
  const isCredit = watchedType === 'credito'

  const submit = (values: FormValues) => {
    const body: Partial<Account> = { name: values.name, type: values.type }
    if (isCredit) {
      body.closing_day = values.closing_day
      body.due_day = values.due_day
    }
    if (isEdit && account) {
      update.mutate({ id: account.id, ...body })
    } else {
      create.mutate(body)
    }
    onClose()
  }

  return (
    <Modal open={open} onClose={onClose} title={isEdit ? 'Editar cuenta' : 'Nueva cuenta'}>
      <form onSubmit={handleSubmit(submit)} style={{ display: 'grid', gap: 12 }}>
        <div>
          <input
            {...register('name')}
            placeholder="Nombre de la cuenta"
            style={inputStyle}
          />
          {errors.name && <span style={errorStyle}>{errors.name.message}</span>}
        </div>

        <Controller
          name="type"
          control={control}
          render={({ field }) => (
            <Select
              value={field.value}
              onValueChange={(v) => field.onChange(v)}
              options={TYPE_OPTS}
              ariaLabel="Tipo de cuenta"
              style={{ width: '100%' }}
            />
          )}
        />

        {isCredit && (
          <>
            <label style={labelStyle}>
              Día de cierre
              <input
                type="number"
                {...register('closing_day', { valueAsNumber: true })}
                style={inputStyle}
              />
              {errors.closing_day && <span style={errorStyle}>{errors.closing_day.message}</span>}
            </label>
            <label style={labelStyle}>
              Día de vencimiento
              <input
                type="number"
                {...register('due_day', { valueAsNumber: true })}
                style={inputStyle}
              />
              {errors.due_day && <span style={errorStyle}>{errors.due_day.message}</span>}
            </label>
          </>
        )}

        <button type="submit" style={ctaBtn}>Guardar</button>
      </form>
    </Modal>
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
const ctaBtn: React.CSSProperties = {
  background: 'var(--color-voltage)',
  color: 'var(--voltage-on-dark)',
  border: 'none',
  borderRadius: 10,
  padding: '14px',
  fontWeight: 500,
  cursor: 'pointer',
}
const errorStyle: React.CSSProperties = { fontSize: 12, color: 'var(--color-error)', marginTop: 2 }
