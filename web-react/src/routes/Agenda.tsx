import { useEffect, useState } from 'react'
import { useEventos, useEventosMutations } from '../hooks/useEventos'
import { useRecordatorios, useRecordatoriosMutations, type SnoozePreset } from '../hooks/useRecordatorios'
import { useMe } from '../hooks/useMe'
import { useHouseholdMembers, useShareMutation } from '../hooks/useShare'
import { type Evento, type Recordatorio, type HouseholdMember } from '../lib/types'
import { cleanReminderText } from '../lib/format'
import Card from '../components/ui/Card'
import CardActions from '../components/ui/CardActions'
import Modal from '../components/ui/Modal'
import Select from '../components/ui/Select'
import ConfirmDialog from '../components/ui/ConfirmDialog'
import EmptyState from '../components/ui/EmptyState'
import ShareSheet from '../components/ui/ShareSheet'
import ShareBadge from '../components/ui/ShareBadge'
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

function recurrenceLabel(rec?: string | null): string | null {
  if (rec === 'daily') return 'se repite todos los días'
  if (rec === 'weekly') return 'se repite cada semana'
  if (rec === 'monthly') return 'se repite cada mes'
  return null
}

// 'YYYY-MM-DDTHH:MM' en hora local (para las ocurrencias proyectadas).
function toLocalDT(d: Date): string {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

// Ocurrencias de un evento: si es recurrente, proyecta las próximas (hasta maxCount,
// dentro del horizonte); si no, una sola. Solo de hoy en adelante. Así la agenda
// muestra que se repite (varios días) sin cambiar el modelo del backend.
function eventOccurrences(e: Evento, maxCount = 8, horizonDays = 120): string[] {
  if (!e.recurrence) return [e.starts_at]
  const startToday = new Date(); startToday.setHours(0, 0, 0, 0)
  const horizon = new Date(); horizon.setDate(horizon.getDate() + horizonDays)
  const d = new Date(e.starts_at)
  const out: string[] = []
  let guard = 0
  while (out.length < maxCount && d <= horizon && guard < 400) {
    if (d >= startToday) out.push(toLocalDT(d))
    if (e.recurrence === 'daily') d.setDate(d.getDate() + 1)
    else if (e.recurrence === 'monthly') d.setMonth(d.getMonth() + 1)
    else d.setDate(d.getDate() + 7) // weekly (default)
    guard++
  }
  return out.length ? out : [e.starts_at]
}

const WEEKDAY_ABBR = ['DOM', 'LUN', 'MAR', 'MIÉ', 'JUE', 'VIE', 'SÁB']

// ── unified item type ────────────────────────────────────────────────────────

type AgendaItem =
  | { kind: 'evento'; data: Evento; sortKey: string; occursAt: string }
  | { kind: 'recordatorio'; data: Recordatorio; sortKey: string }

// ── Evento modal (rediseño 2b: chips de cuándo + recordatorio + compartir) ────

type EventoInitial = { title: string; starts_at: string; location?: string; notes?: string }
type EventoPayload = {
  title: string
  starts_at: string
  location: string
  notes: string
  reminder_offsets?: number[]
  share?: boolean
}

function pad(n: number) { return String(n).padStart(2, '0') }
function todayStr() { const d = new Date(); return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}` }
function addDaysStr(days: number) {
  const d = new Date(); d.setDate(d.getDate() + days)
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}
function nextSaturdayStr() {
  const d = new Date()
  const delta = (6 - d.getDay() + 7) % 7 || 7 // próximo sábado (nunca hoy)
  d.setDate(d.getDate() + delta)
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

function EventoModal({
  open,
  onClose,
  title,
  initial,
  withReminders = false,
  partnerLabel,
  onSubmit,
}: {
  open: boolean
  onClose: () => void
  title: string
  initial?: EventoInitial
  withReminders?: boolean
  partnerLabel?: string | null
  onSubmit: (data: EventoPayload) => void
}) {
  const [name, setName] = useState('')
  const [dateStr, setDateStr] = useState(todayStr())
  const [timeStr, setTimeStr] = useState('09:00')
  const [pickDate, setPickDate] = useState(false)
  const [reminder, setReminder] = useState<'1h' | '1d' | 'none'>('1h')
  const [location, setLocation] = useState('')
  const [notes, setNotes] = useState('')
  const [share, setShare] = useState(false)
  const [err, setErr] = useState(false)

  // Reset al abrir; precargar valores en edición.
  useEffect(() => {
    if (!open) return
    if (initial) {
      const d = new Date(initial.starts_at)
      setName(initial.title)
      setDateStr(`${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`)
      setTimeStr(`${pad(d.getHours())}:${pad(d.getMinutes())}`)
      setLocation(initial.location ?? '')
      setNotes(initial.notes ?? '')
    } else {
      setName(''); setDateStr(todayStr()); setTimeStr('09:00'); setLocation(''); setNotes('')
    }
    setPickDate(false); setReminder('1h'); setShare(false); setErr(false)
  }, [open, initial])

  const sat = nextSaturdayStr()
  const quick: { key: string; label: string; val: string }[] = [
    { key: 'hoy', label: 'Hoy', val: todayStr() },
    { key: 'manana', label: 'Mañana', val: addDaysStr(1) },
    { key: 'sabado', label: 'Sábado', val: sat },
  ]

  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!name.trim()) { setErr(true); return }
    const reminder_offsets = withReminders
      ? (reminder === '1h' ? [60] : reminder === '1d' ? [1440] : [])
      : undefined
    onSubmit({
      title: name.trim(),
      starts_at: `${dateStr}T${timeStr}`,
      location: location.trim(),
      notes: notes.trim(),
      reminder_offsets,
      share: withReminders ? share : undefined,
    })
  }

  return (
    <Modal open={open} onClose={onClose} title={title}>
      <form onSubmit={submit} style={{ display: 'grid', gap: 14 }}>
        <div>
          <input
            value={name}
            onChange={(e) => { setName(e.target.value); if (err) setErr(false) }}
            placeholder="Título del evento"
            autoFocus
            style={{ ...inputStyle, border: `1.6px solid ${err ? 'var(--color-error)' : 'var(--color-obsidian-ink)'}`, fontWeight: 500 }}
          />
          {err && <span style={errorStyle}>Poné un título</span>}
        </div>

        <div>
          <div style={groupLabel}>Cuándo</div>
          <div style={{ display: 'flex', gap: 7, flexWrap: 'wrap' }}>
            {quick.map((q) => (
              <button key={q.key} type="button" onClick={() => { setDateStr(q.val); setPickDate(false) }} style={chip(!pickDate && dateStr === q.val)}>
                {q.label}
              </button>
            ))}
            <button type="button" onClick={() => setPickDate(true)} style={chip(pickDate || !quick.some((q) => q.val === dateStr))}>
              Elegir fecha
            </button>
          </div>
          {(pickDate || !quick.some((q) => q.val === dateStr)) && (
            <input type="date" value={dateStr} onChange={(e) => setDateStr(e.target.value)} style={{ ...inputStyle, marginTop: 9 }} />
          )}
          <div style={{ display: 'flex', gap: 9, marginTop: 9 }}>
            <label style={{ ...fieldBox, flex: 1 }}>
              <span style={miniLabel}>Hora</span>
              <input type="time" value={timeStr} onChange={(e) => setTimeStr(e.target.value)} style={bareInput} />
            </label>
            <label style={{ ...fieldBox, flex: 1 }}>
              <span style={miniLabel}>Lugar (opcional)</span>
              <input value={location} onChange={(e) => setLocation(e.target.value)} placeholder="—" style={bareInput} />
            </label>
          </div>
        </div>

        {withReminders && (
          <div>
            <div style={groupLabel}>Recordatorio</div>
            <div style={{ display: 'flex', gap: 7, flexWrap: 'wrap' }}>
              <button type="button" onClick={() => setReminder('1h')} style={chip(reminder === '1h')}>1 h antes</button>
              <button type="button" onClick={() => setReminder('1d')} style={chip(reminder === '1d')}>1 día antes</button>
              <button type="button" onClick={() => setReminder('none')} style={chip(reminder === 'none')}>Sin aviso</button>
            </div>
          </div>
        )}

        <textarea value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Notas (opcional)" rows={2} style={{ ...inputStyle, resize: 'vertical' }} />

        {withReminders && partnerLabel && (
          <label style={shareRow}>
            <span style={{ flex: 1, fontSize: 13, fontWeight: 500 }}>Compartir con {partnerLabel}</span>
            <button type="button" role="switch" aria-checked={share} aria-label={`Compartir con ${partnerLabel}`} onClick={() => setShare((s) => !s)} style={toggleTrack(share)}>
              <span style={toggleKnob(share)} />
            </button>
          </label>
        )}

        <button type="submit" style={solidCta}>Guardar evento</button>
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
  events,
  onSubmit,
}: {
  open: boolean
  onClose: () => void
  title: string
  initial?: { text?: string; remind_at?: string; event_id?: number | null }
  events: Evento[]
  onSubmit: (data: { text: string; remind_at: string; event_id: number | null }) => void
}) {
  const [text, setText] = useState('')
  const [remindAt, setRemindAt] = useState('')
  const [eventId, setEventId] = useState<string>('none')
  const [err, setErr] = useState(false)

  useEffect(() => {
    if (!open) return
    setText(initial?.text ?? '')
    setRemindAt(initial?.remind_at ? initial.remind_at.slice(0, 16) : '')
    setEventId(initial?.event_id ? String(initial.event_id) : 'none')
    setErr(false)
  }, [open, initial])

  const eventOpts = [
    { value: 'none', label: 'Sin evento' },
    ...events.map((e) => ({ value: String(e.id), label: `${e.title} · ${fmtDateLabel(e.starts_at)} ${fmtTime(e.starts_at)}` })),
  ]

  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!text.trim() || !remindAt) { setErr(true); return }
    onSubmit({ text: text.trim(), remind_at: remindAt, event_id: eventId === 'none' ? null : Number(eventId) })
  }

  return (
    <Modal open={open} onClose={onClose} title={title}>
      <form onSubmit={submit} style={{ display: 'grid', gap: 12 }}>
        <div>
          <input
            value={text}
            onChange={(e) => { setText(e.target.value); if (err) setErr(false) }}
            placeholder="¿De qué te recordamos?"
            autoFocus
            style={{ ...inputStyle, border: '1.6px solid var(--color-obsidian-ink)', fontWeight: 500 }}
          />
          {err && !text.trim() && <span style={errorStyle}>Requerido</span>}
        </div>
        <label style={labelStyle}>
          Recordar a las
          <input type="datetime-local" value={remindAt} onChange={(e) => setRemindAt(e.target.value)} style={inputStyle} />
          {err && !remindAt && <span style={errorStyle}>Elegí fecha y hora</span>}
        </label>
        <label style={labelStyle}>
          Vincular a un evento (opcional)
          <Select value={eventId} onValueChange={setEventId} options={eventOpts} ariaLabel="Evento" style={{ width: '100%' }} />
        </label>
        <button type="submit" style={solidCta}>Guardar</button>
      </form>
    </Modal>
  )
}

// ── Snooze picker ────────────────────────────────────────────────────────────

function SnoozeMenu({ onSnooze }: { onSnooze: (p: SnoozePreset) => void }) {
  return (
    <div style={{ display: 'flex', gap: 6, marginTop: 8 }}>
      {(['1h', 'manana', 'semana'] as SnoozePreset[]).map((p) => (
        <button key={p} type="button" onClick={() => onSnooze(p)} style={chip(false)}>
          {p === '1h' ? '+1 h' : p === 'manana' ? 'Mañana' : 'Semana'}
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
  const shareEv = useShareMutation('eventos')
  const { data: me } = useMe()
  const { data: members } = useHouseholdMembers()

  const [addMode, setAddMode] = useState<AddMode>(null)
  const [editEvento, setEditEvento] = useState<Evento | null>(null)
  const [editRec, setEditRec] = useState<Recordatorio | null>(null)
  const [deleteItem, setDeleteItem] = useState<AgendaItem | null>(null)
  const [shareItem, setShareItem] = useState<AgendaItem | null>(null)
  const [selectedDay, setSelectedDay] = useState<string | null>(null)

  const memberById = new Map<number, HouseholdMember>((members ?? []).map((m) => [m.id, m]))
  const others = (members ?? []).filter((m) => !m.is_me)
  const partnerLabel = others.length === 1 ? others[0].name : others.length > 1 ? 'el plan' : null

  if (loadE || loadR) return <MovimientosSkeleton />

  const allEventos = [...(eventos ?? []), ...(eventosPast ?? [])]
  const allItems: AgendaItem[] = [
    ...allEventos.flatMap((e): AgendaItem[] =>
      eventOccurrences(e).map((occ) => ({ kind: 'evento' as const, data: e, sortKey: occ, occursAt: occ }))),
    ...(recordatorios ?? []).filter((r) => !r.event_id).map((r): AgendaItem => ({ kind: 'recordatorio', data: r, sortKey: r.remind_at })),
  ].sort((a, b) => a.sortKey.localeCompare(b.sortKey))

  const groups = new Map<string, AgendaItem[]>()
  for (const item of allItems) {
    const key = dayKey(item.sortKey)
    if (!groups.has(key)) groups.set(key, [])
    groups.get(key)!.push(item)
  }

  // Cosas de acá a fin de semana (para el subtítulo)
  const weekEnd = new Date(); weekEnd.setDate(weekEnd.getDate() + 7)
  const thisWeekCount = allItems.filter((i) => !isPast(i.sortKey) && new Date(i.sortKey) <= weekEnd).length
  const monthName = new Intl.DateTimeFormat('es-AR', { month: 'long' }).format(new Date())

  // Tira de días = SOLO los días que tienen algo, de hoy en adelante (los vacíos no
  // se muestran). Tocar un día filtra la lista a ese día; "Todos" limpia el filtro.
  const todayKey = localDay(new Date())
  const dayKeys = [...groups.keys()].filter((k) => k >= todayKey).sort()
  const activeDay = selectedDay && dayKeys.includes(selectedDay) ? selectedDay : null

  const handleCreateEvento = (data: EventoPayload) => {
    evMut.create.mutate(
      {
        title: data.title,
        starts_at: data.starts_at,
        location: data.location || null,
        notes: data.notes || null,
        reminder_offsets: data.reminder_offsets,
      },
      {
        onSuccess: (res) => {
          if (data.share && res?.id) shareEv.mutate({ id: res.id, shared: 1 })
        },
      },
    )
    setAddMode(null)
  }
  const handleCreateRec = (data: { text: string; remind_at: string; event_id: number | null }) => {
    recMut.create.mutate({ text: data.text, remind_at: data.remind_at, event_id: data.event_id })
    setAddMode(null)
  }
  const handleEditEvento = (data: EventoPayload) => {
    if (!editEvento) return
    evMut.update.mutate({ id: editEvento.id, title: data.title, starts_at: data.starts_at, location: data.location || null, notes: data.notes || null })
    setEditEvento(null)
  }
  const handleEditRec = (data: { text: string; remind_at: string; event_id: number | null }) => {
    if (!editRec) return
    recMut.update.mutate({ id: editRec.id, text: data.text, remind_at: data.remind_at, event_id: data.event_id })
    setEditRec(null)
  }
  const handleDelete = () => {
    if (!deleteItem) return
    if (deleteItem.kind === 'evento') evMut.remove.mutate(deleteItem.data.id)
    else recMut.remove.mutate(deleteItem.data.id)
    setDeleteItem(null)
  }

  return (
    <div style={{ padding: '10px 18px 24px' }}>
      {/* Título */}
      <div style={pageTitle}>Agenda</div>
      <div style={pageSub}>
        <span style={{ textTransform: 'capitalize' }}>{monthName}</span> · {thisWeekCount} cosa{thisWeekCount === 1 ? '' : 's'} esta semana
      </div>

      {/* Acciones de creación */}
      <div style={{ display: 'flex', gap: 8, margin: '16px 0 12px' }}>
        <button onClick={() => setAddMode('evento')} style={solidPill}>
          <i className="ti ti-plus" aria-hidden /> Evento
        </button>
        <button onClick={() => setAddMode('recordatorio')} style={ghostPill}>
          <i className="ti ti-plus" aria-hidden /> Recordatorio
        </button>
      </div>

      {/* Tira de días con algo (los vacíos no se muestran). Tocar un día filtra a ese día. */}
      {dayKeys.length > 0 && (
        <div style={{ display: 'flex', gap: 6, paddingBottom: 14, borderBottom: '1px solid var(--color-mist)', overflowX: 'auto' }}>
          {activeDay && (
            <button
              onClick={() => setSelectedDay(null)}
              style={{ flex: 'none', borderRadius: 12, padding: '0 13px', border: '1px solid var(--color-mist)', background: 'transparent', color: 'var(--color-obsidian-ink)', fontSize: 11.5, fontWeight: 600, cursor: 'pointer' }}
            >
              Todos
            </button>
          )}
          {dayKeys.map((key) => {
            const d = new Date(key + 'T00:00')
            const isToday = key === todayKey
            const isSel = key === activeDay
            const fg = isSel ? 'var(--voltage-on-dark)' : isToday ? 'var(--color-linen)' : undefined
            return (
              <button
                key={key}
                onClick={() => setSelectedDay(isSel ? null : key)}
                aria-pressed={isSel}
                style={{
                  flex: 'none', width: 44, borderRadius: 12, padding: '8px 0', textAlign: 'center', cursor: 'pointer',
                  border: 'none', background: isSel ? 'var(--color-voltage)' : isToday ? 'var(--color-obsidian-ink)' : 'transparent',
                }}
              >
                <div style={{ fontSize: 9.5, fontWeight: 500, color: fg ?? 'var(--color-sage)' }}>{WEEKDAY_ABBR[d.getDay()]}</div>
                <div className="num-serif" style={{ fontSize: 16, fontWeight: 600, color: fg ?? 'var(--color-obsidian-ink)' }}>{d.getDate()}</div>
                <div style={{ height: 4, marginTop: 2, display: 'flex', justifyContent: 'center' }}>
                  <span style={{ width: 4, height: 4, borderRadius: '50%', background: isSel ? 'var(--voltage-on-dark)' : 'var(--color-voltage)' }} />
                </div>
              </button>
            )
          })}
        </div>
      )}

      {/* Empty state */}
      {allItems.length === 0 && (
        <EmptyState>Sin eventos ni recordatorios. ¡Agregá algo!</EmptyState>
      )}

      {/* Días agrupados (filtrados al día seleccionado si hay uno) */}
      {[...groups.entries()].filter(([dateKey]) => !activeDay || dateKey === activeDay).map(([dateKey, items]) => (
        <div key={dateKey} id={`day-${dateKey}`} style={{ marginTop: 16 }}>
          <div style={{ ...sectionLabel, textTransform: 'uppercase' }}>{fmtDateLabel(dateKey + 'T00:00')}</div>
          <div style={{ display: 'grid', gap: 9 }}>
            {items.map((item) =>
              item.kind === 'evento' ? (
                <EventoCard
                  key={`e-${item.data.id}-${item.occursAt}`}
                  evento={item.data}
                  occursAt={item.occursAt}
                  isOwner={me?.id === item.data.user_id}
                  owner={memberById.get(item.data.user_id)}
                  dimmed={isPast(item.occursAt)}
                  onEdit={() => setEditEvento(item.data)}
                  onDelete={() => setDeleteItem(item)}
                  onShare={() => setShareItem(item)}
                  onRemoveReminder={(rid) => recMut.remove.mutate(rid)}
                />
              ) : (
                <RecordatorioCard
                  key={`r-${item.data.id}`}
                  rec={item.data}
                  isOwner={me?.id === item.data.user_id}
                  owner={memberById.get(item.data.user_id)}
                  dimmed={isPast(item.data.remind_at)}
                  onEdit={() => setEditRec(item.data)}
                  onDelete={() => setDeleteItem(item)}
                  onShare={() => setShareItem(item)}
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
        partnerLabel={partnerLabel}
        onSubmit={handleCreateEvento}
      />
      <RecordatorioModal
        open={addMode === 'recordatorio'}
        onClose={() => setAddMode(null)}
        title="Nuevo recordatorio"
        events={eventos ?? []}
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
        events={eventos ?? []}
        initial={editRec ? { text: editRec.text, remind_at: editRec.remind_at, event_id: editRec.event_id } : undefined}
        onSubmit={handleEditRec}
      />

      {/* Delete confirm */}
      <ConfirmDialog
        open={deleteItem !== null}
        onOpenChange={(o) => { if (!o) setDeleteItem(null) }}
        title="¿Borrar este ítem?"
        description={
          deleteItem?.kind === 'evento'
            ? `Se eliminará "${deleteItem.data.title}"${deleteItem.data.recurrence ? ' y todas sus repeticiones' : ''}.`
            : deleteItem?.kind === 'recordatorio'
            ? `Se eliminará "${deleteItem.data.text}".`
            : ''
        }
        onConfirm={handleDelete}
      />

      {/* Share sheet */}
      <ShareSheet
        open={shareItem !== null}
        onClose={() => setShareItem(null)}
        entity={shareItem?.kind === 'evento' ? 'eventos' : 'recordatorios'}
        id={shareItem?.data.id ?? null}
      />
    </div>
  )
}

// ── sub-components ───────────────────────────────────────────────────────────

function MemberDot({ member }: { member: HouseholdMember }) {
  return (
    <span
      title={member.name}
      style={{
        width: 18, height: 18, borderRadius: '50%', flexShrink: 0,
        background: member.color || 'rgba(43,238,75,0.22)', color: 'var(--voltage-on-dark)',
        fontSize: 9, fontWeight: 600, display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
      }}
    >
      {member.name.slice(0, 1).toUpperCase()}
    </span>
  )
}

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
  occursAt,
  isOwner,
  owner,
  dimmed,
  onEdit,
  onDelete,
  onShare,
  onRemoveReminder,
}: {
  evento: Evento
  occursAt: string
  isOwner: boolean
  owner?: HouseholdMember
  dimmed: boolean
  onEdit: () => void
  onDelete: () => void
  onShare: () => void
  onRemoveReminder: (id: number) => void
}) {
  const reminders = evento.reminders ?? []
  const isRecurring = !!evento.recurrence
  // En un evento recurrente el aviso ligado se va corriendo semana a semana → no
  // mostramos el offset exacto por ocurrencia (sería confuso), sino "con aviso" + el
  // cartel de recurrencia. En eventos simples, el detalle exacto de siempre.
  const sub = [
    evento.location,
    !isRecurring && reminders[0] ? `recordatorio ${reminderOffsetLabel(reminders[0].remind_at, evento.starts_at)}` : null,
    isRecurring && reminders.length ? 'con aviso' : null,
  ].filter(Boolean).join(' · ')
  return (
    <Card style={{ opacity: dimmed ? 0.55 : 1, padding: 14 }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 11 }}>
        <div style={{ ...timeCol }}>{fmtTime(occursAt)}</div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 13.5, fontWeight: 600, color: 'var(--color-obsidian-ink)' }}>{evento.title}</div>
          {(sub || evento.notes) && (
            <div style={{ fontSize: 11.5, color: 'var(--color-sage)', marginTop: 2 }}>{sub || evento.notes}</div>
          )}
          {isRecurring && (
            <div style={{ display: 'inline-flex', alignItems: 'center', gap: 4, marginTop: 6, fontSize: 10.5, fontWeight: 600, color: 'var(--color-voltage-ink, #1f7a2e)', background: 'rgba(43,238,75,0.12)', borderRadius: 999, padding: '3px 8px' }}>
              <i className="ti ti-repeat" aria-hidden style={{ fontSize: 11 }} /> {recurrenceLabel(evento.recurrence)}
            </div>
          )}
          {isOwner && <div style={{ marginTop: 6 }}><ShareBadge shared={evento.shared} count={evento.share_count} /></div>}
          {!isRecurring && reminders.length > 0 && (
            <div style={{ marginTop: 8, display: 'grid', gap: 5 }}>
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
        </div>
        {!isOwner && owner && <MemberDot member={owner} />}
        <CardActions
          onShare={isOwner ? onShare : undefined}
          onEdit={onEdit}
          onDelete={isOwner ? onDelete : undefined}
        />
      </div>
    </Card>
  )
}

function RecordatorioCard({
  rec,
  isOwner,
  owner,
  dimmed,
  onEdit,
  onDelete,
  onShare,
  onSnooze,
}: {
  rec: Recordatorio
  isOwner: boolean
  owner?: HouseholdMember
  dimmed: boolean
  onEdit: () => void
  onDelete: () => void
  onShare: () => void
  onSnooze: (p: SnoozePreset) => void
}) {
  const [showSnooze, setShowSnooze] = useState(false)

  return (
    <Card style={{ opacity: dimmed ? 0.55 : 1, padding: 14 }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 11 }}>
        <i className="ti ti-bell" aria-hidden style={{ fontSize: 16, color: 'var(--color-sage)', marginTop: 2 }} />
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 13.5, fontWeight: 600, color: 'var(--color-obsidian-ink)' }}>{cleanReminderText(rec.text)}</div>
          <div style={{ fontSize: 11.5, color: 'var(--color-sage)', marginTop: 2 }}>Recordatorio · {fmtTime(rec.remind_at)}</div>
          {recurrenceLabel(rec.recurrence) && (
            <div style={{ display: 'inline-flex', alignItems: 'center', gap: 4, marginTop: 5, fontSize: 10.5, fontWeight: 600, color: 'var(--color-voltage-ink, #1f7a2e)', background: 'rgba(43,238,75,0.12)', borderRadius: 999, padding: '3px 8px' }}>
              <i className="ti ti-repeat" aria-hidden style={{ fontSize: 11 }} /> {recurrenceLabel(rec.recurrence)}
            </div>
          )}
          {isOwner && <div style={{ marginTop: 6 }}><ShareBadge shared={rec.shared} count={rec.share_count} /></div>}
          {showSnooze && (
            <SnoozeMenu
              onSnooze={(p) => { onSnooze(p); setShowSnooze(false) }}
            />
          )}
        </div>
        {!isOwner && owner && <MemberDot member={owner} />}
        <button onClick={() => setShowSnooze((v) => !v)} style={{ ...ghostPill, padding: '5px 10px', fontSize: 11 }}>
          Posponer
        </button>
        <CardActions
          onShare={isOwner ? onShare : undefined}
          onEdit={onEdit}
          onDelete={isOwner ? onDelete : undefined}
        />
      </div>
    </Card>
  )
}

// ── styles ───────────────────────────────────────────────────────────────────

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
const errorStyle: React.CSSProperties = { fontSize: 12, color: 'var(--color-error)', marginTop: 4, display: 'block' }
const groupLabel: React.CSSProperties = { fontSize: 10, fontWeight: 600, letterSpacing: '0.1em', textTransform: 'uppercase', color: 'var(--color-sage)', marginBottom: 8 }
const miniLabel: React.CSSProperties = { fontSize: 10, color: 'var(--color-sage)', display: 'block' }
const fieldBox: React.CSSProperties = { border: '1px solid var(--color-mist)', borderRadius: 12, padding: '8px 12px', display: 'grid', gap: 2, boxSizing: 'border-box' }
const bareInput: React.CSSProperties = { border: 'none', background: 'transparent', fontSize: 14, color: 'var(--color-obsidian-ink)', padding: 0, width: '100%', outline: 'none' }

const shareRow: React.CSSProperties = { display: 'flex', alignItems: 'center', gap: 11, borderTop: '1px solid var(--color-mist)', paddingTop: 14 }

function toggleTrack(on: boolean): React.CSSProperties {
  return {
    width: 40, height: 22, borderRadius: 9999, border: 'none', cursor: 'pointer', position: 'relative', flexShrink: 0,
    background: on ? 'var(--color-voltage)' : 'var(--color-mist)', transition: 'background .15s', padding: 0,
  }
}
function toggleKnob(on: boolean): React.CSSProperties {
  return {
    position: 'absolute', top: 2, left: on ? 20 : 2, width: 18, height: 18, borderRadius: '50%', background: '#fff', transition: 'left .15s',
  }
}

const solidCta: React.CSSProperties = {
  background: 'var(--color-voltage)',
  color: 'var(--voltage-on-dark)',
  border: 'none',
  borderRadius: 12,
  padding: '14px',
  fontWeight: 600,
  fontSize: 14,
  cursor: 'pointer',
}
const solidPill: React.CSSProperties = {
  display: 'inline-flex', alignItems: 'center', gap: 5,
  background: 'var(--color-voltage)', color: 'var(--voltage-on-dark)', border: 'none',
  borderRadius: 9999, padding: '9px 15px', fontSize: 12.5, fontWeight: 600, cursor: 'pointer',
}
const ghostPill: React.CSSProperties = {
  display: 'inline-flex', alignItems: 'center', gap: 5,
  background: 'transparent', color: 'var(--color-obsidian-ink)', border: '1px solid var(--color-mist)',
  borderRadius: 9999, padding: '9px 15px', fontSize: 12.5, fontWeight: 600, cursor: 'pointer',
}
const sectionLabel: React.CSSProperties = {
  fontSize: 10,
  fontWeight: 600,
  letterSpacing: '0.1em',
  color: 'var(--color-sage)',
  textTransform: 'uppercase',
  marginBottom: 8,
}
const timeCol: React.CSSProperties = {
  fontSize: 12, fontWeight: 600, color: 'var(--color-sage)', width: 40, flexShrink: 0, fontVariantNumeric: 'tabular-nums', marginTop: 1,
}

function chip(active: boolean): React.CSSProperties {
  return {
    fontSize: 11.5, fontWeight: 600, padding: '7px 12px', borderRadius: 9999, cursor: 'pointer',
    border: active ? '1px solid var(--color-voltage)' : '1px solid var(--color-mist)',
    background: active ? 'var(--color-voltage)' : 'transparent',
    color: active ? 'var(--voltage-on-dark)' : 'var(--color-obsidian-ink)',
  }
}
