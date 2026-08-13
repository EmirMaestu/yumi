import { useState } from 'react'
import { useForm, Controller } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useHabitos, useHabitosMutations } from '../hooks/useHabitos'
import { type HabitoResumen, type HabitoLog } from '../lib/types'
import Card from '../components/ui/Card'
import CardActions from '../components/ui/CardActions'
import Modal from '../components/ui/Modal'
import ConfirmDialog from '../components/ui/ConfirmDialog'
import EmptyState from '../components/ui/EmptyState'
import { MovimientosSkeleton } from '../components/ui/skeletons'

// Últimos 7 días (claves YYYY-MM-DD). Se mantiene el criterio previo (toISOString)
// para no cambiar el bucketing respecto de logged_at.slice(0,10).
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
    <Modal open={open} onClose={() => { onClose(); reset(); setCustomName(false) }} title="Nuevo hábito">
      <form onSubmit={handleSubmit(submit)} style={{ display: 'grid', gap: 12 }}>
        {!customName && (
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            {suggestions.slice(0, 12).map((s) => (
              <button key={s} type="button" onClick={() => setValue('name', s)} style={chipBtn}>{s}</button>
            ))}
            <button type="button" onClick={() => setCustomName(true)} style={{ ...chipBtn, borderStyle: 'dashed' }}>Otro…</button>
          </div>
        )}

        <div>
          <Controller
            name="name"
            control={control}
            render={({ field }) => (
              <input {...field} value={field.value ?? ''} placeholder="Nombre del hábito" style={{ ...inputStyle, border: '1.6px solid var(--color-obsidian-ink)', fontWeight: 500 }} />
            )}
          />
          {errors.name && <span style={errorStyle}>{errors.name.message}</span>}
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
          <label style={labelStyle}>
            Valor (opcional)
            <input type="number" step="any" {...register('value', { valueAsNumber: true, setValueAs: (v) => (v === '' || isNaN(v) ? null : Number(v)) })} style={inputStyle} />
          </label>
          <label style={labelStyle}>
            Unidad (opcional)
            <input {...register('unit')} placeholder="km, min, vasos…" style={inputStyle} />
          </label>
        </div>

        <label style={labelStyle}>
          Nota (opcional)
          <input {...register('note')} placeholder="Breve comentario…" style={inputStyle} />
        </label>

        <button type="submit" style={solidCta}>Registrar</button>
      </form>
    </Modal>
  )
}

// racha actual: días consecutivos con registro terminando hoy (o ayer si hoy no hay)
function currentStreak(days: Set<string>, last7: string[]): number {
  const today = last7[last7.length - 1]
  const d = new Date(today + 'T12:00:00')
  // si hoy no tiene, arrancamos desde ayer (la racha sigue viva hasta hoy)
  if (!days.has(today)) d.setDate(d.getDate() - 1)
  let streak = 0
  while (days.has(d.toISOString().slice(0, 10))) {
    streak++
    d.setDate(d.getDate() - 1)
  }
  return streak
}

export default function Habitos() {
  const { data, isLoading } = useHabitos(30) // 30d para calcular rachas largas
  const { create, update, remove } = useHabitosMutations()
  const [modalOpen, setModalOpen] = useState(false)
  const [renameTarget, setRenameTarget] = useState<string | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null)

  const last7 = getLast7Days()

  const handleCreate = (values: FormValues) => {
    create.mutate({ name: values.name, value: values.value ?? null, unit: values.unit || null, note: values.note || null })
    setModalOpen(false)
  }

  const idsForName = (name: string, items: HabitoLog[]) => items.filter((l) => l.name === name).map((l) => l.id)
  const handleRename = async (name: string, newName: string, items: HabitoLog[]) => {
    for (const id of idsForName(name, items)) await update.mutateAsync({ id, name: newName })
    setRenameTarget(null)
  }
  const handleDelete = async (name: string, items: HabitoLog[]) => {
    for (const id of idsForName(name, items)) await remove.mutateAsync(id)
    setDeleteTarget(null)
  }

  if (isLoading) return <MovimientosSkeleton />

  const resumen = data?.resumen ?? []
  const items = data?.items ?? []
  const today = last7[last7.length - 1]

  // name → set de días con registro
  const logsByName: Record<string, Set<string>> = {}
  // name → id del registro de HOY (para poder destildar)
  const todayLogId: Record<string, number> = {}
  for (const log of items) {
    const day = log.logged_at.slice(0, 10)
    if (!logsByName[log.name]) logsByName[log.name] = new Set()
    logsByName[log.name].add(day)
    if (day === today && todayLogId[log.name] == null) todayLogId[log.name] = log.id
  }

  const doneToday = resumen.filter((r) => logsByName[r.name]?.has(today)).length

  // Semana agregada: por cada día, cuántos hábitos se cumplieron
  const weekRatio = last7.map((d) => {
    if (resumen.length === 0) return 0
    const n = resumen.filter((r) => logsByName[r.name]?.has(d)).length
    return n / resumen.length
  })

  const toggleToday = (name: string) => {
    if (logsByName[name]?.has(today)) {
      const id = todayLogId[name]
      if (id != null) remove.mutate(id)
    } else {
      create.mutate({ name })
    }
  }

  return (
    <div style={{ padding: '10px 18px 24px' }}>
      {/* Título */}
      <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between' }}>
        <div>
          <div style={pageTitle}>Hábitos</div>
          <div style={pageSub}>{doneToday} de {resumen.length} hecho{resumen.length === 1 ? '' : 's'} hoy</div>
        </div>
        <button onClick={() => setModalOpen(true)} style={solidPill}><i className="ti ti-plus" aria-hidden /> Nuevo</button>
      </div>

      {resumen.length === 0 && (
        <div style={{ marginTop: 16 }}>
          <EmptyState>Sin hábitos registrados. ¡Empezá hoy!</EmptyState>
        </div>
      )}

      {/* Semana */}
      {resumen.length > 0 && (
        <Card style={{ padding: 15, marginTop: 16 }}>
          <div style={sectionLabel}>Esta semana</div>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 12 }}>
            {last7.map((d, i) => {
              const ratio = weekRatio[i]
              const bg = ratio >= 1 ? 'var(--color-voltage)' : ratio > 0 ? 'rgba(43,238,75,0.35)' : 'var(--color-mist)'
              const isToday = d === today
              return (
                <div key={d} style={{ textAlign: 'center' }}>
                  <div style={{ width: 26, height: 26, borderRadius: '50%', background: bg, margin: '0 auto', border: isToday ? '2px solid var(--color-obsidian-ink)' : 'none', boxSizing: 'border-box' }} />
                  <div style={{ fontSize: 9.5, color: 'var(--color-sage)', marginTop: 5, fontWeight: 500 }}>
                    {DAY_ABBR[new Date(d + 'T12:00:00').getDay()]}
                  </div>
                </div>
              )
            })}
          </div>
        </Card>
      )}

      {/* Hoy: tildar desde la fila + racha a la derecha */}
      {resumen.length > 0 && (
        <div style={{ marginTop: 16 }}>
          <div style={sectionLabel}>Hoy</div>
          <div style={{ display: 'grid', gap: 9 }}>
            {resumen.map((r) => {
              const done = logsByName[r.name]?.has(today) ?? false
              const streak = currentStreak(logsByName[r.name] ?? new Set(), last7)
              return (
                <Card key={r.name} style={{ padding: '13px 14px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                    <button
                      onClick={() => toggleToday(r.name)}
                      aria-label={done ? `Destildar ${r.name}` : `Tildar ${r.name}`}
                      style={{
                        width: 22, height: 22, borderRadius: '50%', flexShrink: 0,
                        border: `1.7px solid ${done ? 'var(--color-voltage)' : 'var(--color-mist)'}`,
                        background: done ? 'var(--color-voltage)' : 'transparent',
                        display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer',
                      }}
                    >
                      {done && <i className="ti ti-check" style={{ fontSize: 13, color: 'var(--voltage-on-dark)' }} aria-hidden />}
                    </button>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: 13.5, fontWeight: 500, color: 'var(--color-obsidian-ink)' }}>{r.name}</div>
                      {r.total > 0 && r.unit && (
                        <div style={{ fontSize: 11, color: 'var(--color-sage)', marginTop: 1 }}>{r.total} {r.unit} · 7 días</div>
                      )}
                    </div>
                    <span style={{ fontSize: 11.5, fontWeight: 600, color: streak > 0 ? 'var(--color-obsidian-ink)' : 'var(--color-sage)' }}>
                      {streak > 0 ? `${streak} día${streak === 1 ? '' : 's'}${streak >= 5 ? ' 🔥' : ''}` : 'Racha 0'}
                    </span>
                    <CardActions onEdit={() => setRenameTarget(r.name)} onDelete={() => setDeleteTarget(r.name)} />
                  </div>
                </Card>
              )
            })}
            <button onClick={() => setModalOpen(true)} style={dashedRow}>
              <i className="ti ti-plus" aria-hidden /> Nuevo hábito
            </button>
          </div>
        </div>
      )}

      {/* Register modal */}
      <RegistrarModal open={modalOpen} onClose={() => setModalOpen(false)} onSubmit={handleCreate} resumen={resumen} />

      {/* Rename habit */}
      <Modal open={renameTarget !== null} onClose={() => setRenameTarget(null)} title="Renombrar hábito">
        <RenameForm key={renameTarget ?? ''} initial={renameTarget ?? ''} onSubmit={(v) => handleRename(renameTarget!, v, items)} />
      </Modal>

      {/* Delete habit confirm */}
      <ConfirmDialog
        open={deleteTarget !== null}
        onOpenChange={(o) => { if (!o) setDeleteTarget(null) }}
        title="¿Borrar este hábito?"
        description={deleteTarget ? `Se borrarán todos los registros de "${deleteTarget}".` : ''}
        onConfirm={() => { if (deleteTarget) handleDelete(deleteTarget, items) }}
      />
    </div>
  )
}

function RenameForm({ initial, onSubmit }: { initial: string; onSubmit: (v: string) => void }) {
  const [name, setName] = useState(initial)
  return (
    <form onSubmit={(e) => { e.preventDefault(); if (name.trim()) onSubmit(name.trim()) }} style={{ display: 'grid', gap: 12 }}>
      <input value={name} onChange={(e) => setName(e.target.value)} autoFocus placeholder="Nombre del hábito" style={inputStyle} />
      <button type="submit" style={solidCta}>Guardar</button>
    </form>
  )
}

const pageTitle: React.CSSProperties = { fontFamily: 'var(--font-serif)', fontWeight: 600, fontSize: 30, lineHeight: 1.05, color: 'var(--color-obsidian-ink)' }
const pageSub: React.CSSProperties = { fontSize: 12.5, color: 'var(--color-sage)', marginTop: 3 }
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
const errorStyle: React.CSSProperties = { fontSize: 12, color: 'var(--color-error)', marginTop: 2 }
const solidCta: React.CSSProperties = {
  background: 'var(--color-voltage)', color: 'var(--voltage-on-dark)', border: 'none',
  borderRadius: 12, padding: '14px', fontWeight: 600, fontSize: 14, cursor: 'pointer',
}
const solidPill: React.CSSProperties = {
  display: 'inline-flex', alignItems: 'center', gap: 5,
  background: 'var(--color-voltage)', color: 'var(--voltage-on-dark)', border: 'none',
  borderRadius: 9999, padding: '9px 15px', fontSize: 12.5, fontWeight: 600, cursor: 'pointer',
}
const sectionLabel: React.CSSProperties = {
  fontSize: 10, fontWeight: 600, letterSpacing: '0.1em', color: 'var(--color-sage)', textTransform: 'uppercase', marginBottom: 8,
}
const dashedRow: React.CSSProperties = {
  display: 'flex', alignItems: 'center', gap: 6, justifyContent: 'center',
  border: '1px dashed var(--color-mist)', borderRadius: 14, padding: '13px 14px',
  fontSize: 13, fontWeight: 600, color: 'var(--color-sage)', background: 'transparent', cursor: 'pointer',
}
const chipBtn: React.CSSProperties = {
  background: 'transparent', border: '1px solid var(--color-mist)', borderRadius: 9999,
  padding: '4px 12px', fontSize: 12, cursor: 'pointer', color: 'var(--color-obsidian-ink)',
}
