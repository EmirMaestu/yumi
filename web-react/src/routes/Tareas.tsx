import { useState } from 'react'
import { useForm, Controller } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useTareas, useTareasMutations } from '../hooks/useTareas'
import { useMe } from '../hooks/useMe'
import { type Tarea } from '../lib/types'
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
            style={inputStyle}
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
          <input
            type="date"
            {...register('due_at')}
            style={inputStyle}
          />
        </label>

        <button type="submit" style={ctaBtn}>Guardar</button>
      </form>
    </Modal>
  )
}

const PRIORITY_ORDER = { alta: 0, media: 1, baja: 2 }

export default function Tareas() {
  const { data, isLoading } = useTareas('all')
  const { create, update, done, undone, remove } = useTareasMutations()
  const { data: me } = useMe()

  const [newOpen, setNewOpen] = useState(false)
  const [editItem, setEditItem] = useState<Tarea | null>(null)
  const [deleteItem, setDeleteItem] = useState<Tarea | null>(null)
  const [shareItem, setShareItem] = useState<Tarea | null>(null)

  const pendientes = (data ?? [])
    .filter((t) => t.status === 'pendiente')
    .sort((a, b) => PRIORITY_ORDER[a.priority] - PRIORITY_ORDER[b.priority])

  const hechas = (data ?? [])
    .filter((t) => t.status === 'hecha')
    .sort((a, b) => (b.completed_at ?? '').localeCompare(a.completed_at ?? ''))

  const handleCreate = (values: FormValues) => {
    create.mutate({
      text: values.text,
      priority: values.priority,
      due_at: values.due_at || null,
    })
    setNewOpen(false)
  }

  const handleEdit = (values: FormValues) => {
    if (!editItem) return
    update.mutate({
      id: editItem.id,
      text: values.text,
      priority: values.priority,
      due_at: values.due_at || null,
    })
    setEditItem(null)
  }

  if (isLoading) return <MovimientosSkeleton />

  return (
    <div style={{ padding: '14px 18px 24px', display: 'grid', gap: 14 }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center' }}>
        <div className="cap" style={{ flex: 1 }}>Tareas</div>
        <button onClick={() => setNewOpen(true)} style={ghostBtn}>+ Nueva</button>
      </div>

      {/* Pendientes */}
      {pendientes.length === 0 && hechas.length === 0 && (
        <EmptyState>Sin tareas. ¡Agregá una!</EmptyState>
      )}

      {pendientes.length > 0 && (
        <div style={{ display: 'grid', gap: 10 }}>
          {pendientes.map((t) => (
            <TareaRow
              key={t.id}
              tarea={t}
              isOwner={me?.id === t.user_id}
              onToggle={() => done.mutate(t.id)}
              onEdit={() => setEditItem(t)}
              onDelete={() => setDeleteItem(t)}
              onShare={() => setShareItem(t)}
            />
          ))}
        </div>
      )}

      {/* Hechas */}
      {hechas.length > 0 && (
        <div>
          <div style={{ fontSize: 11, fontWeight: 600, letterSpacing: '0.08em', color: 'var(--color-sage)', textTransform: 'uppercase', marginBottom: 8 }}>
            Completadas
          </div>
          <div style={{ display: 'grid', gap: 8 }}>
            {hechas.map((t) => (
              <TareaRow
                key={t.id}
                tarea={t}
                isOwner={me?.id === t.user_id}
                onToggle={() => undone.mutate(t.id)}
                onEdit={() => setEditItem(t)}
                onDelete={() => setDeleteItem(t)}
                onShare={() => setShareItem(t)}
                dimmed
              />
            ))}
          </div>
        </div>
      )}

      {/* New modal */}
      <TareaModal
        open={newOpen}
        onClose={() => setNewOpen(false)}
        title="Nueva tarea"
        onSubmit={handleCreate}
      />

      {/* Edit modal */}
      <TareaModal
        key={editItem ? `t-${editItem.id}` : 't-edit'}
        open={editItem !== null}
        onClose={() => setEditItem(null)}
        title="Editar tarea"
        initial={editItem ? {
          text: editItem.text,
          priority: editItem.priority,
          due_at: editItem.due_at ?? '',
        } : undefined}
        onSubmit={handleEdit}
      />

      {/* Share sheet */}
      <ShareSheet
        open={shareItem !== null}
        onClose={() => setShareItem(null)}
        entity="tareas"
        id={shareItem?.id ?? null}
      />

      {/* Delete confirm */}
      <ConfirmDialog
        open={deleteItem !== null}
        onOpenChange={(o) => { if (!o) setDeleteItem(null) }}
        title="¿Borrar esta tarea?"
        description={deleteItem ? `Se eliminará "${deleteItem.text}".` : ''}
        onConfirm={() => {
          if (deleteItem) remove.mutate(deleteItem.id)
          setDeleteItem(null)
        }}
      />
    </div>
  )
}

function TareaRow({
  tarea,
  isOwner,
  onToggle,
  onEdit,
  onDelete,
  onShare,
  dimmed = false,
}: {
  tarea: Tarea
  isOwner: boolean
  onToggle: () => void
  onEdit: () => void
  onDelete: () => void
  onShare: () => void
  dimmed?: boolean
}) {
  const PRIORITY_COLOR_MAP: Record<string, string> = {
    alta: '#c0392b',
    media: 'var(--color-sage)',
    baja: 'var(--color-mist)',
  }

  return (
    <Card style={{ opacity: dimmed ? 0.55 : 1 }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
        {/* Checkbox */}
        <button
          onClick={onToggle}
          aria-label={tarea.status === 'hecha' ? 'Marcar pendiente' : 'Marcar hecha'}
          style={{
            width: 20,
            height: 20,
            borderRadius: '50%',
            border: `2px solid ${tarea.status === 'hecha' ? 'var(--color-voltage)' : 'var(--color-mist)'}`,
            background: tarea.status === 'hecha' ? 'var(--color-voltage)' : 'transparent',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            cursor: 'pointer',
            flexShrink: 0,
            marginTop: 2,
          }}
        >
          {tarea.status === 'hecha' && (
            <i className="ti ti-check" style={{ fontSize: 12, color: 'var(--voltage-on-dark)' }} aria-hidden />
          )}
        </button>

        {/* Content */}
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{
            fontSize: 14,
            fontWeight: 500,
            textDecoration: dimmed ? 'line-through' : 'none',
            color: dimmed ? 'var(--color-sage)' : 'var(--color-obsidian-ink)',
          }}>
            {tarea.text}
          </div>
          <div style={{ display: 'flex', gap: 8, marginTop: 3, flexWrap: 'wrap' }}>
            <span style={{
              fontSize: 11,
              color: PRIORITY_COLOR_MAP[tarea.priority],
              fontWeight: 600,
              textTransform: 'uppercase',
              letterSpacing: '0.04em',
            }}>
              {tarea.priority}
            </span>
            {tarea.due_at && (
              <span style={{ fontSize: 11, color: 'var(--color-sage)' }}>
                <i className="ti ti-calendar" aria-hidden /> {tarea.due_at.slice(0, 10)}
              </span>
            )}
            {isOwner && <ShareBadge shared={tarea.shared} count={tarea.share_count} />}
          </div>
        </div>

        <CardActions
          onShare={isOwner ? onShare : undefined}
          onEdit={isOwner ? onEdit : undefined}
          onDelete={isOwner ? onDelete : undefined}
        />
      </div>
    </Card>
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
const errorStyle: React.CSSProperties = { fontSize: 12, color: 'var(--color-error)', marginTop: 2 }
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
