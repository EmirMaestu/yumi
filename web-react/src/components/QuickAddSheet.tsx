import { useState, useEffect } from 'react'
import { type SubmitHandler, useForm, Controller } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import Sheet from './ui/Sheet'
import Select from './ui/Select'
import { useAccounts } from '../hooks/useAccounts'
import { useCategories } from '../hooks/useCategories'
import { useTxMutations, useTransferMutation } from '../hooks/useTransactions'
import { useTareasMutations } from '../hooks/useTareas'
import { useNotasMutations } from '../hooks/useNotas'
import { useEventosMutations } from '../hooks/useEventos'
import { useRecordatoriosMutations } from '../hooks/useRecordatorios'
import { parseAmount } from '../lib/parseAmount'
import { todayISODate, dateToNoonISO } from '../lib/format'
import { CURRENCY_CODES, CURRENCY_OPTS } from '../lib/currencies'
import { apiGet } from '../lib/api'

// ---------- quick-type selector ----------
type QuickType = 'gasto' | 'tarea' | 'nota' | 'evento' | 'recordatorio'

const QUICK_TYPES: { value: QuickType; label: string }[] = [
  { value: 'gasto', label: 'Gasto' },
  { value: 'tarea', label: 'Tarea' },
  { value: 'nota', label: 'Nota' },
  { value: 'evento', label: 'Evento' },
  { value: 'recordatorio', label: 'Recordatorio' },
]

// ---------- schemas ----------
const txSchema = z.object({
  type: z.enum(['gasto', 'ingreso']),
  amount: z.preprocess((v) => parseAmount(String(v)), z.number().positive('Monto inválido')),
  description: z.string().min(1, 'Falta descripción'),
  account_id: z.coerce.number().int(),
  category_id: z.coerce.number().int().optional(),
  currency: z.enum(CURRENCY_CODES).default('ARS'),
  occurred_at: z.string(),
})
type TxInput = z.input<typeof txSchema>
type TxOutput = z.output<typeof txSchema>

const transferSchema = z.object({
  from_account_id: z.string().min(1, 'Elegí la cuenta de origen'),
  to_account_id: z.string().min(1, 'Elegí la cuenta de destino'),
  amount: z.preprocess((v) => parseAmount(String(v)), z.number().positive('Monto inválido')),
  occurred_at: z.string(),
}).refine((d) => d.from_account_id !== d.to_account_id, { message: 'Elegí dos cuentas distintas', path: ['to_account_id'] })
type TransferInput = z.input<typeof transferSchema>
type TransferOutput = z.output<typeof transferSchema>

const tareaSchema = z.object({
  text: z.string().min(1, 'Falta texto'),
  priority: z.enum(['alta', 'media', 'baja']),
})
type TareaInput = z.infer<typeof tareaSchema>

const notaSchema = z.object({
  text: z.string().min(1, 'Falta texto'),
  tags: z.string(), // comma-separated, parsed on submit
})
type NotaInput = z.infer<typeof notaSchema>

const eventoSchema = z.object({
  title: z.string().min(1, 'Falta título'),
  starts_at: z.string().min(1, 'Falta fecha/hora'),
  location: z.string().optional(),
})
type EventoInput = z.infer<typeof eventoSchema>

const recordatorioSchema = z.object({
  text: z.string().min(1, 'Falta texto'),
  remind_at: z.string().min(1, 'Falta fecha/hora'),
})
type RecordatorioInput = z.infer<typeof recordatorioSchema>

// ---------- shared styles ----------
const fieldStyle: React.CSSProperties = {
  border: '1px solid var(--color-mist)', borderRadius: 10, padding: '12px 14px',
  fontSize: 16, background: 'transparent', width: '100%', boxSizing: 'border-box',
}
const ctaStyle: React.CSSProperties = {
  background: 'var(--color-voltage)', color: 'var(--voltage-on-dark)', border: 'none',
  borderRadius: 10, padding: '14px', fontWeight: 500, boxShadow: 'var(--shadow-cta)', cursor: 'pointer',
}
const errStyle: React.CSSProperties = { color: 'var(--color-error)', fontSize: 12 }

// ---------- sub-forms ----------

function GastoForm({ onClose }: { onClose: () => void }) {
  const [tipo, setTipo] = useState<'gasto' | 'ingreso' | 'transferencia'>('gasto')
  const tipoOpts = [
    { value: 'gasto', label: 'Gasto' },
    { value: 'ingreso', label: 'Ingreso' },
    { value: 'transferencia', label: 'Transferencia' },
  ]
  return (
    <div style={{ display: 'grid', gap: 12 }}>
      <Select value={tipo} onValueChange={(v) => setTipo(v as typeof tipo)} options={tipoOpts} placeholder="Tipo…" ariaLabel="Tipo" style={{ width: '100%' }} />
      {tipo === 'transferencia'
        ? <TransferForm onClose={onClose} />
        : <NormalTxForm key={tipo} tipo={tipo} onClose={onClose} />}
    </div>
  )
}

function NormalTxForm({ tipo, onClose }: { tipo: 'gasto' | 'ingreso'; onClose: () => void }) {
  const accounts = useAccounts()
  const categories = useCategories()
  const { create } = useTxMutations()
  const { register, handleSubmit, control, watch, setValue, formState: { errors } } = useForm<TxInput, unknown, TxOutput>({
    resolver: zodResolver(txSchema),
    defaultValues: { type: tipo, currency: 'ARS', occurred_at: todayISODate() },
  })
  const [suggested, setSuggested] = useState(false)
  const desc = watch('description')
  const catVal = watch('category_id')
  // Auto-categorización sugerida (debounce 500ms) si el Select está vacío.
  useEffect(() => {
    if (!desc || catVal) return
    const id = setTimeout(async () => {
      try {
        const r = await apiGet<{ category_id: number | null }>(`/api/categories/suggest?description=${encodeURIComponent(desc)}`)
        if (r.category_id) { setValue('category_id', r.category_id); setSuggested(true) }
      } catch { /* silencioso: la sugerencia es best-effort */ }
    }, 500)
    return () => clearTimeout(id)
  }, [desc, catVal, setValue])

  const onSubmit: SubmitHandler<TxOutput> = (v) =>
    create.mutate({ ...v, occurred_at: dateToNoonISO(v.occurred_at) }, { onSuccess: onClose })
  const accountOpts = (accounts.data ?? []).map((a) => ({ value: String(a.id), label: a.name }))
  const categoryOpts = (categories.data ?? []).map((c) => ({ value: String(c.id), label: c.name }))

  return (
    <form onSubmit={handleSubmit(onSubmit)} style={{ display: 'grid', gap: 12 }}>
      <div style={{ display: 'flex', gap: 8 }}>
        <input {...register('amount')} inputMode="decimal" placeholder="Monto" style={{ ...fieldStyle, flex: 1, minWidth: 0 }} />
        <Controller name="currency" control={control} render={({ field }) => (
          <Select value={field.value} onValueChange={field.onChange} options={CURRENCY_OPTS} ariaLabel="Moneda" style={{ width: 104 }} />
        )} />
      </div>
      {errors.amount && <small style={errStyle}>{errors.amount.message}</small>}
      <input {...register('description')} placeholder="Descripción" style={fieldStyle} />
      {errors.description && <small style={errStyle}>{errors.description.message}</small>}
      <Controller name="account_id" control={control} render={({ field }) => (
        <Select value={field.value ? String(field.value) : undefined} onValueChange={(v) => field.onChange(Number(v))} options={accountOpts} placeholder="Cuenta…" ariaLabel="Cuenta" style={{ width: '100%' }} />
      )} />
      <div style={{ display: 'grid', gap: 4 }}>
        <Controller name="category_id" control={control} render={({ field }) => (
          <Select value={field.value ? String(field.value) : undefined} onValueChange={(v) => { field.onChange(Number(v)); setSuggested(false) }} options={categoryOpts} placeholder="Categoría (opcional)…" ariaLabel="Categoría" style={{ width: '100%' }} />
        )} />
        {suggested && Boolean(catVal) && <span style={{ fontSize: 11, color: 'var(--color-sage)' }}>Sugerida — podés cambiarla</span>}
      </div>
      <label style={{ display: 'grid', gap: 4, fontSize: 13, color: 'var(--color-sage)' }}>
        Fecha
        <input type="date" {...register('occurred_at')} style={fieldStyle} />
      </label>
      <button type="submit" disabled={create.isPending} style={ctaStyle}>{create.isPending ? 'Guardando…' : 'Guardar →'}</button>
    </form>
  )
}

function TransferForm({ onClose }: { onClose: () => void }) {
  const accounts = useAccounts()
  const transfer = useTransferMutation()
  const { register, handleSubmit, control, watch, formState: { errors } } = useForm<TransferInput, unknown, TransferOutput>({
    resolver: zodResolver(transferSchema),
    defaultValues: { occurred_at: todayISODate() },
  })
  const from = watch('from_account_id')
  const to = watch('to_account_id')
  const opts = (accounts.data ?? []).map((a) => ({ value: String(a.id), label: a.name }))
  const onSubmit: SubmitHandler<TransferOutput> = (v) =>
    transfer.mutate({
      from_account_id: Number(v.from_account_id),
      to_account_id: Number(v.to_account_id),
      amount: v.amount,
      occurred_at: dateToNoonISO(v.occurred_at),
    }, { onSuccess: onClose })

  return (
    <form onSubmit={handleSubmit(onSubmit)} style={{ display: 'grid', gap: 12 }}>
      <Controller name="from_account_id" control={control} render={({ field }) => (
        <Select value={field.value} onValueChange={field.onChange} options={opts.filter((o) => o.value !== to)} placeholder="Desde…" ariaLabel="Cuenta de origen" style={{ width: '100%' }} />
      )} />
      {errors.from_account_id && <small style={errStyle}>{errors.from_account_id.message}</small>}
      <Controller name="to_account_id" control={control} render={({ field }) => (
        <Select value={field.value} onValueChange={field.onChange} options={opts.filter((o) => o.value !== from)} placeholder="Hacia…" ariaLabel="Cuenta de destino" style={{ width: '100%' }} />
      )} />
      {errors.to_account_id && <small style={errStyle}>{errors.to_account_id.message}</small>}
      <input {...register('amount')} inputMode="decimal" placeholder="Monto" style={fieldStyle} />
      {errors.amount && <small style={errStyle}>{errors.amount.message}</small>}
      <label style={{ display: 'grid', gap: 4, fontSize: 13, color: 'var(--color-sage)' }}>
        Fecha
        <input type="date" {...register('occurred_at')} style={fieldStyle} />
      </label>
      <button type="submit" disabled={transfer.isPending} style={ctaStyle}>{transfer.isPending ? 'Guardando…' : 'Transferir →'}</button>
    </form>
  )
}

function TareaForm({ onClose }: { onClose: () => void }) {
  const { create } = useTareasMutations()
  const { register, handleSubmit, control, formState: { errors } } = useForm<TareaInput>({
    resolver: zodResolver(tareaSchema),
    defaultValues: { priority: 'media' },
  })
  const priorityOpts = [
    { value: 'alta', label: 'Alta' },
    { value: 'media', label: 'Media' },
    { value: 'baja', label: 'Baja' },
  ]
  const onSubmit: SubmitHandler<TareaInput> = (v) => create.mutate(v, { onSuccess: onClose })

  return (
    <form onSubmit={handleSubmit(onSubmit)} style={{ display: 'grid', gap: 12 }}>
      <input {...register('text')} placeholder="¿Qué tenés que hacer?" style={fieldStyle} />
      {errors.text && <small style={errStyle}>{errors.text.message}</small>}
      <Controller name="priority" control={control} render={({ field }) => (
        <Select value={field.value} onValueChange={(v) => field.onChange(v)} options={priorityOpts} placeholder="Prioridad…" ariaLabel="Prioridad" style={{ width: '100%' }} />
      )} />
      <button type="submit" disabled={create.isPending} style={ctaStyle}>{create.isPending ? 'Guardando…' : 'Guardar →'}</button>
    </form>
  )
}

function NotaForm({ onClose }: { onClose: () => void }) {
  const { create } = useNotasMutations()
  const { register, handleSubmit, formState: { errors } } = useForm<NotaInput>({
    resolver: zodResolver(notaSchema),
    defaultValues: { tags: '' },
  })
  const onSubmit: SubmitHandler<NotaInput> = (v) => {
    const tags = v.tags.split(',').map((t) => t.trim()).filter(Boolean)
    create.mutate({ text: v.text, tags }, { onSuccess: onClose })
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} style={{ display: 'grid', gap: 12 }}>
      <textarea {...register('text')} placeholder="Escribí tu nota…" rows={4} style={{ ...fieldStyle, resize: 'vertical' }} />
      {errors.text && <small style={errStyle}>{errors.text.message}</small>}
      <input {...register('tags')} placeholder="Etiquetas (separadas por coma, opcional)" style={fieldStyle} />
      <button type="submit" disabled={create.isPending} style={ctaStyle}>{create.isPending ? 'Guardando…' : 'Guardar →'}</button>
    </form>
  )
}

function EventoForm({ onClose }: { onClose: () => void }) {
  const { create } = useEventosMutations()
  const { register, handleSubmit, formState: { errors } } = useForm<EventoInput>({
    resolver: zodResolver(eventoSchema),
    defaultValues: { starts_at: new Date().toISOString().slice(0, 16) },
  })
  const onSubmit: SubmitHandler<EventoInput> = (v) => {
    create.mutate({
      title: v.title,
      starts_at: v.starts_at,
      location: v.location || null,
    }, { onSuccess: onClose })
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} style={{ display: 'grid', gap: 12 }}>
      <input {...register('title')} placeholder="Título del evento" style={fieldStyle} />
      {errors.title && <small style={errStyle}>{errors.title.message}</small>}
      <input {...register('starts_at')} type="datetime-local" style={fieldStyle} />
      {errors.starts_at && <small style={errStyle}>{errors.starts_at.message}</small>}
      <input {...register('location')} placeholder="Lugar (opcional)" style={fieldStyle} />
      <button type="submit" disabled={create.isPending} style={ctaStyle}>{create.isPending ? 'Guardando…' : 'Guardar →'}</button>
    </form>
  )
}

function RecordatorioForm({ onClose }: { onClose: () => void }) {
  const { create } = useRecordatoriosMutations()
  const { register, handleSubmit, formState: { errors } } = useForm<RecordatorioInput>({
    resolver: zodResolver(recordatorioSchema),
    defaultValues: { remind_at: new Date().toISOString().slice(0, 16) },
  })
  const onSubmit: SubmitHandler<RecordatorioInput> = (v) => create.mutate(v, { onSuccess: onClose })

  return (
    <form onSubmit={handleSubmit(onSubmit)} style={{ display: 'grid', gap: 12 }}>
      <input {...register('text')} placeholder="¿De qué querés que te recuerde?" style={fieldStyle} />
      {errors.text && <small style={errStyle}>{errors.text.message}</small>}
      <input {...register('remind_at')} type="datetime-local" style={fieldStyle} />
      {errors.remind_at && <small style={errStyle}>{errors.remind_at.message}</small>}
      <button type="submit" disabled={create.isPending} style={ctaStyle}>{create.isPending ? 'Guardando…' : 'Guardar →'}</button>
    </form>
  )
}

// ---------- pill switcher ----------
function TypeSwitcher({ value, onChange }: { value: QuickType; onChange: (v: QuickType) => void }) {
  return (
    <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 4 }}>
      {QUICK_TYPES.map((t) => (
        <button
          key={t.value}
          type="button"
          onClick={() => onChange(t.value)}
          style={{
            padding: '6px 14px', borderRadius: 20, fontSize: 13, cursor: 'pointer',
            border: value === t.value ? 'none' : '1px solid var(--color-mist)',
            background: value === t.value ? 'var(--color-voltage)' : 'transparent',
            color: value === t.value ? 'var(--voltage-on-dark)' : 'var(--color-sage)',
            fontWeight: value === t.value ? 600 : 400,
          }}
        >
          {t.label}
        </button>
      ))}
    </div>
  )
}

// ---------- main component ----------
export default function QuickAddSheet({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [quickType, setQuickType] = useState<QuickType>('gasto')

  return (
    <Sheet open={open} onClose={onClose} title="Agregar">
      <div style={{ display: 'grid', gap: 16 }}>
        <TypeSwitcher value={quickType} onChange={setQuickType} />
        {quickType === 'gasto' && <GastoForm onClose={onClose} />}
        {quickType === 'tarea' && <TareaForm onClose={onClose} />}
        {quickType === 'nota' && <NotaForm onClose={onClose} />}
        {quickType === 'evento' && <EventoForm onClose={onClose} />}
        {quickType === 'recordatorio' && <RecordatorioForm onClose={onClose} />}
        <p style={{ fontSize: 12, color: 'var(--color-sage)', textAlign: 'center', margin: 0 }}>También podés mandarle un mensaje al bot.</p>
      </div>
    </Sheet>
  )
}
