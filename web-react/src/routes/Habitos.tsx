import { useState } from 'react'
import { useForm, Controller } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useHabitos, useHabitosMutations } from '../hooks/useHabitos'
import { type HabitoResumen } from '../lib/types'
import Card from '../components/ui/Card'
import CardActions from '../components/ui/CardActions'
import Modal from '../components/ui/Modal'
import ConfirmDialog from '../components/ui/ConfirmDialog'
import EmptyState from '../components/ui/EmptyState'
import { MovimientosSkeleton } from '../components/ui/skeletons'

// Last-7-days grid helpers
function getLast7Days(): string[] {
  const days: string[] = []
  for (let i = 6; i >= 0; i--) {
    const d = new Date()
    d.setDate(d.getDate() - i)
    days.push(d.toISOString().slice(0, 10))
  }
  return days
}

const DAY_ABBR = ['D', 'L', 'M', 'X', 'J', 'V', 'S']

const schema = z.object({
  name: z.string().min(1, 'Requerido'),
  value: z.number().optional().nullable(),
  unit: z.string().optional(),
  note: z.string().optional(),
})

type FormValues = z.infer<typeof schema>

const HABIT_SUGGESTIONS = [
  'Agua', 'Ejercicio', 'Lectura', 'Meditación', 'Caminar',
  'Dormir bien', 'Sin azúcar', 'Vitaminas',
]

function RegistrarModal({
  open,
  onClose,
  onSubmit,
  resumen,
}: {
  open: boolean
  onClose: () => void
  onSubmit: (data: FormValues) => void
  resumen: HabitoResumen[]
}) {
  const [customName, setCustomName] = useState(false)
  const { register, handleSubmit, control, reset, setValue, formState: { errors } } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { name: '', value: null, unit: '', note: '' },
  })

  const submit = (data: FormValues) => {
    onSubmit(data)
    reset()
    setCustomName(false)
  }

  const knownNames = resumen.map((r) => r.name)
  const suggestions = [...new Set([...knownNames, ...HABIT_SUGGESTIONS])]

  return (
    <Modal open={open} onClose={() => { onClose(); reset(); setCustomName(false) }} title="Registrar hábito">
      <form onSubmit={handleSubmit(submit)} style={{ display: 'grid', gap: 12 }}>
        {/* Quick-pick chips */}
        {!customName && (
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            {suggestions.slice(0, 12).map((s) => (
              <button
                key={s}
                type="button"
                onClick={() => setValue('name', s)}
                style={chipBtn}
              >
                {s}
              </button>
            ))}
            <button type="button" onClick={() => setCustomName(true)} style={{ ...chipBtn, borderStyle: 'dashed' }}>
              Otro…
            </button>
          </div>
        )}

        <div>
          <Controller
            name="name"
            control={control}
            render={({ field }) => (
              <input
                {...field}
                value={field.value ?? ''}
                placeholder="Nombre del hábito"
                style={inputStyle}
              />
            )}
          />
          {errors.name && <span style={errorStyle}>{errors.name.message}</span>}
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
          <label style={labelStyle}>
            Valor (opcional)
            <input
              type="number"
              step="any"
              {...register('value', { valueAsNumber: true, setValueAs: (v) => (v === '' || isNaN(v) ? null : Number(v)) })}
              style={inputStyle}
            />
          </label>
          <label style={labelStyle}>
            Unidad (opcional)
            <input
              {...register('unit')}
              placeholder="km, min, vasos…"
              style={inputStyle}
            />
          </label>
        </div>

        <label style={labelStyle}>
          Nota (opcional)
          <input {...register('note')} placeholder="Breve comentario…" style={inputStyle} />
        </label>

        <button type="submit" style={ctaBtn}>Registrar</button>
      </form>
    </Modal>
  )
}

export default function Habitos() {
  const { data, isLoading } = useHabitos(7)
  const { create, update, remove } = useHabitosMutations()
  const [modalOpen, setModalOpen] = useState(false)
  const [renameTarget, setRenameTarget] = useState<string | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null)

  const last7 = getLast7Days()

  const handleCreate = (values: FormValues) => {
    create.mutate({
      name: values.name,
      value: values.value ?? null,
      unit: values.unit || null,
      note: values.note || null,
    })
    setModalOpen(false)
  }

  // a "habit" is several logs sharing a name → rename / delete operates on all of them
  const idsForName = (name: string) => (data?.items ?? []).filter((l) => l.name === name).map((l) => l.id)
  const handleRename = async (name: string, newName: string) => {
    for (const id of idsForName(name)) await update.mutateAsync({ id, name: newName })
    setRenameTarget(null)
  }
  const handleDelete = async (name: string) => {
    for (const id of idsForName(name)) await remove.mutateAsync(id)
    setDeleteTarget(null)
  }

  if (isLoading) return <MovimientosSkeleton />

  const resumen = data?.resumen ?? []
  const items = data?.items ?? []

  // Build a map: name → set of dates with a log
  const logsByName: Record<string, Set<string>> = {}
  for (const log of items) {
    const day = log.logged_at.slice(0, 10)
    if (!logsByName[log.name]) logsByName[log.name] = new Set()
    logsByName[log.name].add(day)
  }

  return (
    <div style={{ padding: '14px 18px 24px', display: 'grid', gap: 14 }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center' }}>
        <div className="cap" style={{ flex: 1 }}>Hábitos</div>
        <button onClick={() => setModalOpen(true)} style={ghostBtn}>+ Registrar</button>
      </div>

      {/* Day labels row */}
      {resumen.length > 0 && (
        <div style={{ overflowX: 'auto' }}>
          <div style={{ display: 'grid', gridTemplateColumns: `1fr repeat(7, 32px)`, gap: 4, alignItems: 'center', minWidth: 320 }}>
            {/* Header */}
            <div />
            {last7.map((d) => (
              <div
                key={d}
                style={{ fontSize: 10, color: 'var(--color-sage)', textAlign: 'center', fontWeight: 600, textTransform: 'uppercase' }}
              >
                {DAY_ABBR[new Date(d + 'T12:00:00').getDay()]}
              </div>
            ))}

            {/* Per-habit rows */}
            {resumen.map((r) => (
              <HabitRow key={r.name} resumen={r} last7={last7} logs={logsByName[r.name] ?? new Set()} />
            ))}
          </div>
        </div>
      )}

      {resumen.length === 0 && (
        <EmptyState>Sin hábitos registrados en los últimos 7 días. ¡Empezá hoy!</EmptyState>
      )}

      {/* Summary cards */}
      {resumen.length > 0 && (
        <div style={{ display: 'grid', gap: 10 }}>
          <div style={{ fontSize: 11, fontWeight: 600, letterSpacing: '0.08em', color: 'var(--color-sage)', textTransform: 'uppercase' }}>
            Resumen — últimos 7 días
          </div>
          {resumen.map((r) => (
            <Card key={r.name}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 14, fontWeight: 500 }}>{r.name}</div>
                  <div style={{ fontSize: 12, color: 'var(--color-sage)', marginTop: 2 }}>
                    {r.cnt} {r.cnt === 1 ? 'vez' : 'veces'}
                    {r.total > 0 && r.unit ? ` · ${r.total} ${r.unit}` : ''}
                  </div>
                </div>
                {/* Streak progress */}
                <div style={{
                  background: 'var(--color-mist)',
                  borderRadius: 9999,
                  height: 6,
                  width: 70,
                  overflow: 'hidden',
                }}>
                  <div style={{
                    background: 'var(--color-voltage)',
                    height: '100%',
                    width: `${Math.min(100, (r.cnt / 7) * 100)}%`,
                    borderRadius: 9999,
                    transition: 'width 0.3s',
                  }} />
                </div>
                <div style={{ fontSize: 12, color: 'var(--color-sage)', minWidth: 24, textAlign: 'right' }}>
                  {r.cnt}/7
                </div>
                <CardActions onEdit={() => setRenameTarget(r.name)} onDelete={() => setDeleteTarget(r.name)} />
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* Register modal */}
      <RegistrarModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        onSubmit={handleCreate}
        resumen={resumen}
      />

      {/* Rename habit */}
      <Modal open={renameTarget !== null} onClose={() => setRenameTarget(null)} title="Renombrar hábito">
        <RenameForm key={renameTarget ?? ''} initial={renameTarget ?? ''} onSubmit={(v) => handleRename(renameTarget!, v)} />
      </Modal>

      {/* Delete habit confirm */}
      <ConfirmDialog
        open={deleteTarget !== null}
        onOpenChange={(o) => { if (!o) setDeleteTarget(null) }}
        title="¿Borrar este hábito?"
        description={deleteTarget ? `Se borrarán todos los registros de "${deleteTarget}".` : ''}
        onConfirm={() => { if (deleteTarget) handleDelete(deleteTarget) }}
      />
    </div>
  )
}

function RenameForm({ initial, onSubmit }: { initial: string; onSubmit: (v: string) => void }) {
  const [name, setName] = useState(initial)
  return (
    <form onSubmit={(e) => { e.preventDefault(); if (name.trim()) onSubmit(name.trim()) }} style={{ display: 'grid', gap: 12 }}>
      <input value={name} onChange={(e) => setName(e.target.value)} autoFocus placeholder="Nombre del hábito" style={inputStyle} />
      <button type="submit" style={ctaBtn}>Guardar</button>
    </form>
  )
}

function HabitRow({
  resumen,
  last7,
  logs,
}: {
  resumen: HabitoResumen
  last7: string[]
  logs: Set<string>
}) {
  return (
    <>
      <div style={{ fontSize: 13, fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', paddingRight: 8 }}>
        {resumen.name}
      </div>
      {last7.map((d) => (
        <div
          key={d}
          title={logs.has(d) ? `${resumen.name} — ${d}` : d}
          style={{
            width: 28,
            height: 28,
            borderRadius: '50%',
            background: logs.has(d) ? 'var(--color-voltage)' : 'var(--color-mist)',
            margin: '0 auto',
            opacity: logs.has(d) ? 1 : 0.35,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          {logs.has(d) && (
            <i className="ti ti-check" style={{ fontSize: 11, color: 'var(--voltage-on-dark)' }} aria-hidden />
          )}
        </div>
      ))}
    </>
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
const chipBtn: React.CSSProperties = {
  background: 'transparent',
  border: '1px solid var(--color-mist)',
  borderRadius: 9999,
  padding: '4px 12px',
  fontSize: 12,
  cursor: 'pointer',
  color: 'var(--color-obsidian-ink)',
}
