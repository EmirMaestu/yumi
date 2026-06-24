import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useEventos, useEventosMutations } from '../hooks/useEventos'
import { useRecordatorios, useRecordatoriosMutations, type SnoozePreset } from '../hooks/useRecordatorios'
import { type Evento, type Recordatorio } from '../lib/types'
import { cleanReminderText } from '../lib/format'
import Card from '../components/ui/Card'
import CardActions from '../components/ui/CardActions'
import Modal from '../components/ui/Modal'
import ConfirmDialog from '../components/ui/ConfirmDialog'
import EmptyState from '../components/ui/EmptyState'
import { MovimientosSkeleton } from '../components/ui/skeletons'

// ── helpers ─────────────────────────────────────────────────────────────────

function fmtTime(iso: string) {
  const d = new Date(iso)
  return new Intl.DateTimeFormat('es-AR', { hour: '2-digit', minute: '2-digit' }).format(d)
}

// Local-time day key (YYYY-MM-DD). Using toISOString() here would convert to UTC
// and bucket evening events (e.g. 21:00 in UTC-3 Argentina) into the next day.
function localDay(d: Date): string {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

function fmtDateLabel(iso: string): string {
  const d = new Date(iso)
  const today = new Date()
  const tomorrow = new Date(today)
  tomorrow.setDate(today.getDate() + 1)
  if (localDay(d) === localDay(today)) return 'Hoy'
  if (localDay(d) === localDay(tomorrow)) return 'Mañana'
  return new Intl.DateTimeFormat('es-AR', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
  }).format(d)
}

function dayKey(iso: string) {
  return localDay(new Date(iso))
}

function isPast(iso: string) {
  return new Date(iso) < new Date()
}

// ── unified item type ────────────────────────────────────────────────────────

type AgendaItem =
  | { kind: 'evento'; data: Evento; sortKey: string }
  | { kind: 'recordatorio'; data: Recordatorio; sortKey: string }

// ── form schemas ─────────────────────────────────────────────────────────────

const eventoSchema = z.object({
  title: z.string().min(1, 'Requerido'),
  starts_at: z.string().min(1, 'Requerido'),
  location: z.string().optional(),
  notes: z.string().optional(),
})
type EventoForm = z.infer<typeof eventoSchema>

const recSchema = z.object({
  text: z.string().min(1, 'Requerido'),
  remind_at: z.string().min(1, 'Requerido'),
})
type RecForm = z.infer<typeof recSchema>

// ── Evento modal ─────────────────────────────────────────────────────────────

const REMINDER_PRESETS = [
  { min: 10, label: '10 min' },
  { min: 60, label: '1 hora' },
  { min: 120, label: '2 horas' },
  { min: 1440, label: '1 día' },
  { min: 2880, label: '2 días' },
]

function EventoModal({
  open,
  onClose,
  title,
  initial,
  withReminders = false,
  onSubmit,
}: {
  open: boolean
  onClose: () => void
  title: string
  initial?: Partial<EventoForm>
  withReminders?: boolean
  onSubmit: (data: EventoForm & { reminder_offsets?: number[] }) => void
}) {
  const { register, handleSubmit, reset, formState: { errors } } = useForm<EventoForm>({
    resolver: zodResolver(eventoSchema),
    defaultValues: { title: '', starts_at: '', location: '', notes: '', ...initial },
  })
  const [offsets, setOffsets] = useState<number[]>([])

  const close = () => { onClose(); reset(); setOffsets([]) }
  const submit = (data: EventoForm) => {
    onSubmit({ ...data, reminder_offsets: withReminders ? offsets : undefined })
    reset(); setOffsets([])
  }

  return (
    <Modal open={open} onClose={close} title={title}>
      <form onSubmit={handleSubmit(submit)} style={{ display: 'grid', gap: 12 }}>
        <div>
          <input {...register('title')} placeholder="Título del evento" autoFocus style={inputStyle} />
          {errors.title && <span style={errorStyle}>{errors.title.message}</span>}
        </div>
        <label style={labelStyle}>
          Fecha y hora
          <input type="datetime-local" {...register('starts_at')} style={inputStyle} />
          {errors.starts_at && <span style={errorStyle}>{errors.starts_at.message}</span>}
        </label>
        <input {...register('location')} placeholder="Lugar (opcional)" style={inputStyle} />
        <textarea {...register('notes')} placeholder="Notas (opcional)" rows={3} style={{ ...inputStyle, resize: 'vertical' }} />
        {withReminders && (
          <div style={labelStyle}>
            Avisarme antes
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 2 }}>
              {REMINDER_PRESETS.map((p) => {
                const on = offsets.includes(p.min)
                return (
                  <button
                    key={p.min}
                    type="button"
                    onClick={() => setOffsets((o) => (on ? o.filter((x) => x !== p.min) : [...o, p.min]))}
                    style={{
                      fontSize: 12, padding: '5px 11px', borderRadius: 9999, cursor: 'pointer',
                      border: `1px solid ${on ? 'var(--color-voltage)' : 'var(--color-mist)'}`,
                      background: on ? 'var(--color-voltage)' : 'transparent',
                      color: on ? 'var(--voltage-on-dark)' : 'var(--color-sage)',
                      fontWeight: on ? 600 : 400,
                    }}
                  >
                    {p.label}
                  </button>
                )
              })}
            </div>
          </div>
        )}
        <button type="submit" style={ctaBtn}>Guardar</button>
      </form>
    </Modal>
  )
}

// ── Recordatorio modal ───────────────────────────────────────────────────────

function RecordatorioModal({
  open,
  onClose,
  title,
  initial,
  onSubmit,
}: {
  open: boolean
  onClose: () => void
  title: string
  initial?: Partial<RecForm>
  onSubmit: (data: RecForm) => void
}) {
  const { register, handleSubmit, reset, formState: { errors } } = useForm<RecForm>({
    resolver: zodResolver(recSchema),
    defaultValues: { text: '', remind_at: '', ...initial },
  })

  const submit = (data: RecForm) => { onSubmit(data); reset() }

  return (
    <Modal open={open} onClose={() => { onClose(); reset() }} title={title}>
      <form onSubmit={handleSubmit(submit)} style={{ display: 'grid', gap: 12 }}>
        <div>
          <input {...register('text')} placeholder="¿De qué te recordamos?" autoFocus style={inputStyle} />
          {errors.text && <span style={errorStyle}>{errors.text.message}</span>}
        </div>
        <label style={labelStyle}>
          Recordar a las
          <input type="datetime-local" {...register('remind_at')} style={inputStyle} />
          {errors.remind_at && <span style={errorStyle}>{errors.remind_at.message}</span>}
        </label>
        <button type="submit" style={ctaBtn}>Guardar</button>
      </form>
    </Modal>
  )
}

// ── Snooze picker ────────────────────────────────────────────────────────────

function SnoozeMenu({ onSnooze }: { onSnooze: (p: SnoozePreset) => void }) {
  return (
    <div style={{ display: 'flex', gap: 6, marginTop: 6 }}>
      {(['1h', 'manana', 'semana'] as SnoozePreset[]).map((p) => (
        <button
          key={p}
          onClick={() => onSnooze(p)}
          style={{
            fontSize: 11,
            padding: '3px 9px',
            borderRadius: 9999,
            border: '1px solid var(--color-mist)',
            background: 'transparent',
            cursor: 'pointer',
            color: 'var(--color-sage)',
            fontWeight: 500,
          }}
        >
          {p === '1h' ? '+1h' : p === 'manana' ? 'Mañana' : 'Semana'}
        </button>
      ))}
    </div>
  )
}

// ── Add menu ─────────────────────────────────────────────────────────────────

type AddMode = 'evento' | 'recordatorio' | null

// ── main component ───────────────────────────────────────────────────────────

export default function Agenda() {
  const { data: eventos, isLoading: loadE } = useEventos(false)
  const { data: eventosPast } = useEventos(true)
  const { data: recordatorios, isLoading: loadR } = useRecordatorios(false)
  const evMut = useEventosMutations()
  const recMut = useRecordatoriosMutations()

  const [addMode, setAddMode] = useState<AddMode>(null)

  // edit state
  const [editEvento, setEditEvento] = useState<Evento | null>(null)
  const [editRec, setEditRec] = useState<Recordatorio | null>(null)

  // delete state
  const [deleteItem, setDeleteItem] = useState<AgendaItem | null>(null)

  if (loadE || loadR) return <MovimientosSkeleton />

  // combine all items into a unified sorted list
  const allItems: AgendaItem[] = [
    ...(eventos ?? []).map((e): AgendaItem => ({ kind: 'evento', data: e, sortKey: e.starts_at })),
    ...(eventosPast ?? []).map((e): AgendaItem => ({ kind: 'evento', data: e, sortKey: e.starts_at })),
    ...(recordatorios ?? []).filter((r) => !r.event_id).map((r): AgendaItem => ({ kind: 'recordatorio', data: r, sortKey: r.remind_at })),
  ].sort((a, b) => a.sortKey.localeCompare(b.sortKey))

  // group by day
  const groups = new Map<string, AgendaItem[]>()
  for (const item of allItems) {
    const key = dayKey(item.sortKey)
    if (!groups.has(key)) groups.set(key, [])
    groups.get(key)!.push(item)
  }

  const handleCreateEvento = (data: EventoForm & { reminder_offsets?: number[] }) => {
    evMut.create.mutate({
      title: data.title,
      starts_at: data.starts_at,
      location: data.location || null,
      notes: data.notes || null,
      reminder_offsets: data.reminder_offsets,
    })
    setAddMode(null)
  }
  const handleCreateRec = (data: RecForm) => {
    recMut.create.mutate({ text: data.text, remind_at: data.remind_at })
    setAddMode(null)
  }
  const handleEditEvento = (data: EventoForm) => {
    if (!editEvento) return
    evMut.update.mutate({ id: editEvento.id, title: data.title, starts_at: data.starts_at, location: data.location || null, notes: data.notes || null })
    setEditEvento(null)
  }
  const handleEditRec = (data: RecForm) => {
    if (!editRec) return
    recMut.update.mutate({ id: editRec.id, text: data.text, remind_at: data.remind_at })
    setEditRec(null)
  }
  const handleDelete = () => {
    if (!deleteItem) return
    if (deleteItem.kind === 'evento') evMut.remove.mutate(deleteItem.data.id)
    else recMut.remove.mutate(deleteItem.data.id)
    setDeleteItem(null)
  }

  return (
    <div style={{ padding: '14px 18px 24px', display: 'grid', gap: 14 }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <div className="cap" style={{ flex: 1 }}>Agenda</div>
        <button
          onClick={() => setAddMode('evento')}
          style={ghostBtn}
        >
          + Evento
        </button>
        <button
          onClick={() => setAddMode('recordatorio')}
          style={ghostBtn}
        >
          + Recordatorio
        </button>
      </div>

      {/* Empty state */}
      {allItems.length === 0 && (
        <EmptyState>Sin eventos ni recordatorios. ¡Agregá algo!</EmptyState>
      )}

      {/* Grouped days */}
      {[...groups.entries()].map(([dateKey, items]) => (
        <div key={dateKey}>
          <div style={sectionLabel}>{fmtDateLabel(dateKey + 'T00:00')}</div>
          <div style={{ display: 'grid', gap: 8 }}>
            {items.map((item) =>
              item.kind === 'evento' ? (
                <EventoCard
                  key={`e-${item.data.id}`}
                  evento={item.data}
                  dimmed={isPast(item.data.starts_at)}
                  onEdit={() => setEditEvento(item.data)}
                  onDelete={() => setDeleteItem(item)}
                  onRemoveReminder={(rid) => recMut.remove.mutate(rid)}
                />
              ) : (
                <RecordatorioCard
                  key={`r-${item.data.id}`}
                  rec={item.data}
                  dimmed={isPast(item.data.remind_at)}
                  onEdit={() => setEditRec(item.data)}
                  onDelete={() => setDeleteItem(item)}
                  onSnooze={(preset) => recMut.snooze.mutate({ id: item.data.id, preset })}
                />
              ),
            )}
          </div>
        </div>
      ))}

      {/* Add modals */}
      <EventoModal
        open={addMode === 'evento'}
        onClose={() => setAddMode(null)}
        title="Nuevo evento"
        withReminders
        onSubmit={handleCreateEvento}
      />
      <RecordatorioModal
        open={addMode === 'recordatorio'}
        onClose={() => setAddMode(null)}
        title="Nuevo recordatorio"
        onSubmit={handleCreateRec}
      />

      {/* Edit modals */}
      <EventoModal
        key={editEvento ? `ev-${editEvento.id}` : 'ev-edit'}
        open={editEvento !== null}
        onClose={() => setEditEvento(null)}
        title="Editar evento"
        initial={editEvento ? {
          title: editEvento.title,
          starts_at: editEvento.starts_at,
          location: editEvento.location ?? '',
          notes: editEvento.notes ?? '',
        } : undefined}
        onSubmit={handleEditEvento}
      />
      <RecordatorioModal
        key={editRec ? `rec-${editRec.id}` : 'rec-edit'}
        open={editRec !== null}
        onClose={() => setEditRec(null)}
        title="Editar recordatorio"
        initial={editRec ? { text: editRec.text, remind_at: editRec.remind_at } : undefined}
        onSubmit={handleEditRec}
      />

      {/* Delete confirm */}
      <ConfirmDialog
        open={deleteItem !== null}
        onOpenChange={(o) => { if (!o) setDeleteItem(null) }}
        title="¿Borrar este ítem?"
        description={
          deleteItem?.kind === 'evento'
            ? `Se eliminará "${deleteItem.data.title}".`
            : deleteItem?.kind === 'recordatorio'
            ? `Se eliminará "${deleteItem.data.text}".`
            : ''
        }
        onConfirm={handleDelete}
      />
    </div>
  )
}

// ── sub-components ───────────────────────────────────────────────────────────

// Etiqueta del aviso relativo al inicio del evento ("1 día antes", "2 h antes")
function reminderOffsetLabel(remindAt: string, startsAt: string): string {
  const diffMin = Math.round(
    (new Date(startsAt.replace(' ', 'T')).getTime() - new Date(remindAt.replace(' ', 'T')).getTime()) / 60000,
  )
  if (diffMin <= 0) return fmtTime(remindAt)
  if (diffMin < 60) return `${diffMin} min antes`
  if (diffMin < 1440) return `${Math.round(diffMin / 60)} h antes`
  const d = Math.round(diffMin / 1440)
  return `${d} día${d > 1 ? 's' : ''} antes`
}

function EventoCard({
  evento,
  dimmed,
  onEdit,
  onDelete,
  onRemoveReminder,
}: {
  evento: Evento
  dimmed: boolean
  onEdit: () => void
  onDelete: () => void
  onRemoveReminder: (id: number) => void
}) {
  const reminders = evento.reminders ?? []
  return (
    <Card style={{ opacity: dimmed ? 0.55 : 1 }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
        <div style={{ width: 4, borderRadius: 4, background: 'var(--color-voltage)', alignSelf: 'stretch', flexShrink: 0 }} />
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={timeLabel}>{fmtTime(evento.starts_at)}</span>
            <span style={chipStyle('#2bee4b22', 'var(--color-sage)')}>evento</span>
          </div>
          <div style={{ fontSize: 14, fontWeight: 500, marginTop: 2, color: 'var(--color-obsidian-ink)' }}>
            {evento.title}
          </div>
          {evento.location && (
            <div style={{ fontSize: 12, color: 'var(--color-sage)', marginTop: 2 }}>
              <i className="ti ti-map-pin" aria-hidden /> {evento.location}
            </div>
          )}
          {evento.notes && (
            <div style={{ fontSize: 12, color: 'var(--color-sage)', marginTop: 2 }}>{evento.notes}</div>
          )}
        </div>
        <CardActions onEdit={onEdit} onDelete={onDelete} />
      </div>
      {reminders.length > 0 && (
        <div style={{ marginTop: 8, marginLeft: 14, display: 'grid', gap: 5 }}>
          {reminders.map((r) => (
            <div key={r.id} style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11, color: 'var(--color-sage)' }}>
              <i className="ti ti-bell" aria-hidden style={{ fontSize: 12 }} />
              <span style={{ flex: 1 }}>te aviso {reminderOffsetLabel(r.remind_at, evento.starts_at)}</span>
              <button
                onClick={() => onRemoveReminder(r.id)}
                aria-label="Quitar aviso"
                style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--color-sage)', padding: 0, lineHeight: 1 }}
              >
                <i className="ti ti-x" style={{ fontSize: 12 }} aria-hidden />
              </button>
            </div>
          ))}
        </div>
      )}
    </Card>
  )
}

function RecordatorioCard({
  rec,
  dimmed,
  onEdit,
  onDelete,
  onSnooze,
}: {
  rec: Recordatorio
  dimmed: boolean
  onEdit: () => void
  onDelete: () => void
  onSnooze: (p: SnoozePreset) => void
}) {
  const [showSnooze, setShowSnooze] = useState(false)

  return (
    <Card style={{ opacity: dimmed ? 0.55 : 1 }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
        <div style={{ width: 4, borderRadius: 4, background: 'var(--color-mist)', alignSelf: 'stretch', flexShrink: 0 }} />
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={timeLabel}>{fmtTime(rec.remind_at)}</span>
            <span style={chipStyle('var(--color-mist)', 'var(--color-sage)')}>recordatorio</span>
          </div>
          <div style={{ fontSize: 14, fontWeight: 500, marginTop: 2, color: 'var(--color-obsidian-ink)' }}>
            {cleanReminderText(rec.text)}
          </div>
          {dimmed && (
            <button
              onClick={() => setShowSnooze((v) => !v)}
              style={{ ...ghostBtn, marginTop: 6, padding: '4px 10px', fontSize: 12 }}
            >
              <i className="ti ti-clock-snooze" aria-hidden /> Posponer
            </button>
          )}
          {showSnooze && (
            <SnoozeMenu
              onSnooze={(p) => {
                onSnooze(p)
                setShowSnooze(false)
              }}
            />
          )}
        </div>
        <CardActions onEdit={onEdit} onDelete={onDelete} />
      </div>
    </Card>
  )
}

// ── styles ───────────────────────────────────────────────────────────────────

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
const sectionLabel: React.CSSProperties = {
  fontSize: 11,
  fontWeight: 600,
  letterSpacing: '0.08em',
  color: 'var(--color-sage)',
  textTransform: 'uppercase',
  marginBottom: 8,
}
const timeLabel: React.CSSProperties = {
  fontSize: 12,
  color: 'var(--color-sage)',
  fontVariantNumeric: 'tabular-nums',
}

function chipStyle(bg: string, color: string): React.CSSProperties {
  return {
    fontSize: 10,
    fontWeight: 600,
    textTransform: 'uppercase',
    letterSpacing: '0.06em',
    padding: '2px 7px',
    borderRadius: 9999,
    background: bg,
    color,
  }
}
