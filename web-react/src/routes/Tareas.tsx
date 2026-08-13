import { useState } from 'react'
import { useForm, Controller } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useTareas, useTareasMutations } from '../hooks/useTareas'
import { useMe } from '../hooks/useMe'
import { useHouseholdMembers } from '../hooks/useShare'
import { type Tarea, type HouseholdMember } from '../lib/types'
import Card from '../components/ui/Card'
import CardActions from '../components/ui/CardActions'
import Modal from '../components/ui/Modal'
import ConfirmDialog from '../components/ui/ConfirmDialog'
import EmptyState from '../components/ui/EmptyState'
import Select from '../components/ui/Select'
import ShareSheet from '../components/ui/ShareSheet'
import ShareBadge from '../components/ui/ShareBadge'
import { MovimientosSkeleton } from '../components/ui/skeletons'

const PRIORITY_OPTS = [
  { value: 'alta', label: 'Alta' },
  { value: 'media', label: 'Media' },
  { value: 'baja', label: 'Baja' },
]

const PRIORITY_COLOR: Record<string, string> = {
  alta: 'var(--color-error)',
  media: '#e0a325',
  baja: 'var(--color-mist)',
}

const schema = z.object({
  text: z.string().min(1, 'Requerido'),
  priority: z.enum(['alta', 'media', 'baja']),
  due_at: z.string().optional(),
})

type FormValues = z.infer<typeof schema>

function TareaModal({
  open,
  onClose,
  title,
  initial,
  onSubmit,
}: {
  open: boolean
  onClose: () => void
  title: string
  initial?: Partial<FormValues>
  onSubmit: (data: FormValues) => void
}) {
  const { register, handleSubmit, control, reset, formState: { errors } } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { text: '', priority: 'media', due_at: '', ...initial },
  })

  const submit = (data: FormValues) => {
    onSubmit(data)
    reset()
  }

  return (
    <Modal open={open} onClose={() => { onClose(); reset() }} title={title}>
      <form onSubmit={handleSubmit(submit)} style={{ display: 'grid', gap: 12 }}>
        <div>
          <input
            {...register('text')}
            placeholder="¿Qué tenés que hacer?"
            autoFocus
            style={{ ...inputStyle, border: '1.6px solid var(--color-obsidian-ink)', fontWeight: 500 }}
          />
          {errors.text && <span style={errorStyle}>{errors.text.message}</span>}
        </div>

        <Controller
          name="priority"
          control={control}
          render={({ field }) => (
            <Select
              value={field.value}
              onValueChange={(v) => field.onChange(v)}
              options={PRIORITY_OPTS}
              ariaLabel="Prioridad"
              style={{ width: '100%' }}
            />
          )}
        />

        <label style={labelStyle}>
          Fecha límite (opcional)
          <input type="date" {...register('due_at')} style={inputStyle} />
        </label>

        <button type="submit" style={solidCta}>Guardar</button>
      </form>
    </Modal>
  )
}

const PRIORITY_ORDER = { alta: 0, media: 1, baja: 2 }

// límite fin-de-día de hoy (local); tareas con due_at anterior = vencidas
function endOfToday(): number {
  const d = new Date(); d.setHours(23, 59, 59, 999); return d.getTime()
}

type FilterVal = 'all' | 'done' | number // number = user_id de integrante

export default function Tareas() {
  const { data, isLoading } = useTareas('all')
  const { create, update, done, undone, remove } = useTareasMutations()
  const { data: me } = useMe()
  const { data: members } = useHouseholdMembers()

  const [filter, setFilter] = useState<FilterVal>('all')
  const [newOpen, setNewOpen] = useState(false)
  const [editItem, setEditItem] = useState<Tarea | null>(null)
  const [deleteItem, setDeleteItem] = useState<Tarea | null>(null)
  const [shareItem, setShareItem] = useState<Tarea | null>(null)

  const memberById = new Map<number, HouseholdMember>((members ?? []).map((m) => [m.id, m]))

  const all = data ?? []
  const pendientesAll = all.filter((t) => t.status === 'pendiente')
  const hechas = all
    .filter((t) => t.status === 'hecha')
    .sort((a, b) => (b.completed_at ?? '').localeCompare(a.completed_at ?? ''))

  // pendientes visibles según filtro por integrante
  const pendientes = (typeof filter === 'number' ? pendientesAll.filter((t) => t.user_id === filter) : pendientesAll)
    .sort((a, b) => PRIORITY_ORDER[a.priority] - PRIORITY_ORDER[b.priority])

  const eod = endOfToday()
  const vencidas = pendientes.filter((t) => t.due_at && new Date(t.due_at).getTime() < eod && new Date(t.due_at).getTime() < Date.now())
  const restantes = pendientes.filter((t) => !vencidas.includes(t))

  const tuyas = pendientesAll.filter((t) => t.user_id === me?.id).length

  const handleCreate = (values: FormValues) => {
    create.mutate({ text: values.text, priority: values.priority, due_at: values.due_at || null })
    setNewOpen(false)
  }
  const handleEdit = (values: FormValues) => {
    if (!editItem) return
    update.mutate({ id: editItem.id, text: values.text, priority: values.priority, due_at: values.due_at || null })
    setEditItem(null)
  }

  if (isLoading) return <MovimientosSkeleton />

  const showDone = filter === 'done'

  return (
    <div style={{ padding: '10px 18px 24px' }}>
      {/* Título */}
      <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between' }}>
        <div>
          <div style={pageTitle}>Tareas</div>
          <div style={pageSub}>{pendientesAll.length} pendiente{pendientesAll.length === 1 ? '' : 's'} · {tuyas} tuya{tuyas === 1 ? '' : 's'}</div>
        </div>
        <button onClick={() => setNewOpen(true)} style={solidPill}><i className="ti ti-plus" aria-hidden /> Nueva</button>
      </div>

      {/* Filtros */}
      <div style={{ display: 'flex', gap: 7, margin: '16px 0 6px', paddingBottom: 14, borderBottom: '1px solid var(--color-mist)', overflowX: 'auto' }}>
        <button onClick={() => setFilter('all')} style={chip(filter === 'all')}>Todas</button>
        {(members ?? []).map((m) => (
          <button key={m.id} onClick={() => setFilter(m.id)} style={chip(filter === m.id)}>{m.name}</button>
        ))}
        <button onClick={() => setFilter('done')} style={chip(filter === 'done')}>Hechas</button>
      </div>

      {/* Empty */}
      {all.length === 0 && <EmptyState>Sin tareas. ¡Agregá una!</EmptyState>}

      {/* Vista Hechas */}
      {showDone && (
        hechas.length === 0
          ? <EmptyState>Todavía no completaste ninguna tarea.</EmptyState>
          : (
            <div style={{ marginTop: 16 }}>
              <div style={sectionLabel}>Completadas</div>
              <div style={{ display: 'grid', gap: 9 }}>
                {hechas.map((t) => (
                  <TareaRow key={t.id} tarea={t} isOwner={me?.id === t.user_id} owner={memberById.get(t.user_id)}
                    onToggle={() => undone.mutate(t.id)} onEdit={() => setEditItem(t)} onDelete={() => setDeleteItem(t)} onShare={() => setShareItem(t)} dimmed />
                ))}
              </div>
            </div>
          )
      )}

      {/* Vista pendientes agrupadas */}
      {!showDone && (
        <>
          {vencidas.length > 0 && (
            <div style={{ marginTop: 16 }}>
              <div style={{ ...sectionLabel, color: 'var(--color-error)' }}>Vencidas</div>
              <div style={{ display: 'grid', gap: 9 }}>
                {vencidas.map((t) => (
                  <TareaRow key={t.id} tarea={t} isOwner={me?.id === t.user_id} owner={memberById.get(t.user_id)} overdue
                    onToggle={() => done.mutate(t.id)} onEdit={() => setEditItem(t)} onDelete={() => setDeleteItem(t)} onShare={() => setShareItem(t)} />
                ))}
              </div>
            </div>
          )}

          {restantes.length > 0 && (
            <div style={{ marginTop: 16 }}>
              <div style={sectionLabel}>Esta semana</div>
              <div style={{ display: 'grid', gap: 9 }}>
                {restantes.map((t) => (
                  <TareaRow key={t.id} tarea={t} isOwner={me?.id === t.user_id} owner={memberById.get(t.user_id)}
                    onToggle={() => done.mutate(t.id)} onEdit={() => setEditItem(t)} onDelete={() => setDeleteItem(t)} onShare={() => setShareItem(t)} />
                ))}
              </div>
            </div>
          )}

          {all.length > 0 && vencidas.length === 0 && restantes.length === 0 && (
            <EmptyState>Nada pendiente por acá. 🎉</EmptyState>
          )}

          {pendientesAll.length > 0 && (
            <div style={tipBanner}>Tocá una tarea para asignarla, ponerle fecha o convertirla en evento.</div>
          )}
        </>
      )}

      {/* New modal */}
      <TareaModal open={newOpen} onClose={() => setNewOpen(false)} title="Nueva tarea" onSubmit={handleCreate} />

      {/* Edit modal */}
      <TareaModal
        key={editItem ? `t-${editItem.id}` : 't-edit'}
        open={editItem !== null}
        onClose={() => setEditItem(null)}
        title="Editar tarea"
        initial={editItem ? { text: editItem.text, priority: editItem.priority, due_at: editItem.due_at ?? '' } : undefined}
        onSubmit={handleEdit}
      />

      {/* Share sheet */}
      <ShareSheet open={shareItem !== null} onClose={() => setShareItem(null)} entity="tareas" id={shareItem?.id ?? null} />

      {/* Delete confirm */}
      <ConfirmDialog
        open={deleteItem !== null}
        onOpenChange={(o) => { if (!o) setDeleteItem(null) }}
        title="¿Borrar esta tarea?"
        description={deleteItem ? `Se eliminará "${deleteItem.text}".` : ''}
        onConfirm={() => { if (deleteItem) remove.mutate(deleteItem.id); setDeleteItem(null) }}
      />
    </div>
  )
}

function TareaRow({
  tarea,
  isOwner,
  owner,
  overdue = false,
  onToggle,
  onEdit,
  onDelete,
  onShare,
  dimmed = false,
}: {
  tarea: Tarea
  isOwner: boolean
  owner?: HouseholdMember
  overdue?: boolean
  onToggle: () => void
  onEdit: () => void
  onDelete: () => void
  onShare: () => void
  dimmed?: boolean
}) {
  const doneStatus = tarea.status === 'hecha'
  const dueLabel = tarea.due_at
    ? new Intl.DateTimeFormat('es-AR', { day: '2-digit', month: '2-digit' }).format(new Date(tarea.due_at))
    : null

  return (
    <Card style={{ opacity: dimmed ? 0.55 : 1, padding: '13px 14px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 11 }}>
        {/* Barra de prioridad */}
        <span style={{ width: 3, height: 28, borderRadius: 2, background: PRIORITY_COLOR[tarea.priority], flexShrink: 0 }} />

        {/* Checkbox cuadrado */}
        <button
          onClick={onToggle}
          aria-label={doneStatus ? 'Marcar pendiente' : 'Marcar hecha'}
          style={{
            width: 18, height: 18, borderRadius: 5, flexShrink: 0,
            border: `1.6px solid ${doneStatus ? 'var(--color-voltage)' : 'var(--color-mist)'}`,
            background: doneStatus ? 'var(--color-voltage)' : 'transparent',
            display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer',
          }}
        >
          {doneStatus && <i className="ti ti-check" style={{ fontSize: 11, color: 'var(--voltage-on-dark)' }} aria-hidden />}
        </button>

        {/* Contenido */}
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 13.5, fontWeight: 500, textDecoration: dimmed ? 'line-through' : 'none', color: dimmed ? 'var(--color-sage)' : 'var(--color-obsidian-ink)' }}>
            {tarea.text}
          </div>
          <div style={{ display: 'flex', gap: 8, marginTop: 2, flexWrap: 'wrap', alignItems: 'center' }}>
            {doneStatus && tarea.completed_at && (
              <span style={{ fontSize: 11, color: 'var(--color-sage)' }}>Hecha {new Intl.DateTimeFormat('es-AR', { day: '2-digit', month: '2-digit' }).format(new Date(tarea.completed_at))}</span>
            )}
            {!doneStatus && dueLabel && (
              <span style={{ fontSize: 11, color: overdue ? 'var(--color-error)' : 'var(--color-sage)' }}>
                {overdue ? `Vencía el ${dueLabel}` : dueLabel}
              </span>
            )}
            {!doneStatus && !dueLabel && <span style={{ fontSize: 11, color: 'var(--color-sage)' }}>Sin fecha</span>}
            {isOwner && <ShareBadge shared={tarea.shared} count={tarea.share_count} />}
          </div>
        </div>

        {!isOwner && owner && <MemberDot member={owner} />}

        <CardActions
          onShare={isOwner ? onShare : undefined}
          onEdit={isOwner ? onEdit : undefined}
          onDelete={isOwner ? onDelete : undefined}
        />
      </div>
    </Card>
  )
}

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
const tipBanner: React.CSSProperties = {
  marginTop: 20, background: 'rgba(43,238,75,0.10)', borderRadius: 14, padding: '12px 14px',
  fontSize: 12, lineHeight: 1.4, color: 'var(--color-sage)',
}
function chip(active: boolean): React.CSSProperties {
  return {
    flex: 'none', whiteSpace: 'nowrap',
    fontSize: 11.5, fontWeight: 600, padding: '7px 13px', borderRadius: 9999, cursor: 'pointer',
    border: active ? '1px solid var(--color-voltage)' : '1px solid var(--color-mist)',
    background: active ? 'var(--color-voltage)' : 'transparent',
    color: active ? 'var(--voltage-on-dark)' : 'var(--color-obsidian-ink)',
  }
}
