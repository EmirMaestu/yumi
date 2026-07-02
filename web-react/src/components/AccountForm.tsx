import { useEffect } from 'react'
import { useForm, Controller } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useAccountMutations } from '../hooks/useAccounts'
import { type Account } from '../lib/types'
import Modal from './ui/Modal'
import Select from './ui/Select'
import Field from './form/Field'
import TextInput from './form/TextInput'
import PrimaryButton from './form/PrimaryButton'

const schema = z.object({
  name: z.string().min(1, 'Requerido'),
  type: z.enum(['efectivo', 'billetera', 'debito', 'credito', 'banco', 'dolares', 'cripto', 'inversion']),
  closing_day: z.number().min(1, 'Entre 1 y 31').max(31, 'Entre 1 y 31').optional(),
  due_day: z.number().min(1, 'Entre 1 y 31').max(31, 'Entre 1 y 31').optional(),
  credit_limit: z.number().nonnegative('Debe ser ≥ 0').optional(),
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
              credit_limit: account.credit_limit ?? undefined,
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
      body.credit_limit = values.credit_limit ?? null
    }
    const opts = { onSuccess: () => onClose() }
    if (isEdit && account) {
      update.mutate({ id: account.id, ...body }, opts)
    } else {
      create.mutate(body, opts)
    }
  }

  const isPending = create.isPending || update.isPending

  return (
    <Modal open={open} onClose={onClose} title={isEdit ? 'Editar cuenta' : 'Nueva cuenta'}>
      <form onSubmit={handleSubmit(submit)} style={{ display: 'grid', gap: 12 }}>
        <Field error={errors.name?.message}>
          <TextInput {...register('name')} placeholder="Nombre de la cuenta" />
        </Field>

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
            <Field label="Día de cierre" error={errors.closing_day?.message}>
              <TextInput type="number" {...register('closing_day', { valueAsNumber: true })} />
            </Field>
            <Field label="Día de vencimiento" error={errors.due_day?.message}>
              <TextInput type="number" {...register('due_day', { valueAsNumber: true })} />
            </Field>
            <Field label="Límite de crédito (opcional)" error={errors.credit_limit?.message}>
              <TextInput type="number" step="0.01" placeholder="Ej. 2000000"
                {...register('credit_limit', { setValueAs: (v) => (v === '' || v == null ? undefined : Number(v)) })} />
            </Field>
          </>
        )}

        <PrimaryButton type="submit" loading={isPending}>Guardar</PrimaryButton>
      </form>
    </Modal>
  )
}

