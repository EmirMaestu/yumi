import { useState, useEffect } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useNotas, useNotasMutations } from '../hooks/useNotas'
import { useMe } from '../hooks/useMe'
import { type Nota } from '../lib/types'
import Card from '../components/ui/Card'
import CardActions from '../components/ui/CardActions'
import Modal from '../components/ui/Modal'
import ConfirmDialog from '../components/ui/ConfirmDialog'
import EmptyState from '../components/ui/EmptyState'
import ShareSheet from '../components/ui/ShareSheet'
import ShareBadge from '../components/ui/ShareBadge'
import { MovimientosSkeleton } from '../components/ui/skeletons'

const schema = z.object({
  text: z.string().min(1, 'Requerido'),
  description: z.string().optional(),
  tags: z.string(), // comma-separated
})

type FormValues = z.infer<typeof schema>

function NotaModal({
  open,
  onClose,
  title,
  initial,
  onSubmit,
}: {
  open: boolean
  onClose: () => void
  title: string
  initial?: { text: string; tags: string[]; description?: string }
  onSubmit: (text: string, tags: string[], description: string) => void
}) {
  const { register, handleSubmit, reset, formState: { errors } } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      text: initial?.text ?? '',
      description: initial?.description ?? '',
      tags: initial?.tags.join(', ') ?? '',
    },
  })

  useEffect(() => {
    if (open) {
      reset({
        text: initial?.text ?? '',
        description: initial?.description ?? '',
        tags: initial?.tags.join(', ') ?? '',
      })
    }
  }, [open, reset]) // eslint-disable-line react-hooks/exhaustive-deps

  const submit = (data: FormValues) => {
    const tags = data.tags
      .split(',')
      .map((t) => t.trim())
      .filter(Boolean)
    onSubmit(data.text, tags, (data.description ?? '').trim())
    reset()
  }

  return (
    <Modal open={open} onClose={() => { onClose(); reset() }} title={title}>
      <form onSubmit={handleSubmit(submit)} style={{ display: 'grid', gap: 12 }}>
        <div>
          <input
            {...register('text')}
            placeholder="Título de la nota…"
            autoFocus
            style={inputStyle}
          />
          {errors.text && <span style={errorStyle}>{errors.text.message}</span>}
        </div>

        <label style={labelStyle}>
          Descripción (opcional)
          <textarea
            {...register('description')}
            placeholder="Detalle, contenido más largo…"
            rows={5}
            style={{ ...inputStyle, resize: 'vertical' }}
          />
        </label>

        <label style={labelStyle}>
          Etiquetas (opcional, separadas por coma)
          <input
            {...register('tags')}
            placeholder="idea, pendiente, personal…"
            style={inputStyle}
          />
        </label>

        <button type="submit" style={ctaBtn}>Guardar</button>
      </form>
    </Modal>
  )
}

export default function Notas() {
  const [searchQ, setSearchQ] = useState('')
  const { data, isLoading } = useNotas()
  const { create, update, remove } = useNotasMutations()
  const { data: me } = useMe()

  const [newOpen, setNewOpen] = useState(false)
  const [editItem, setEditItem] = useState<Nota | null>(null)
  const [deleteItem, setDeleteItem] = useState<Nota | null>(null)
  const [shareItem, setShareItem] = useState<Nota | null>(null)

  // Client-side filter
  const filtered = (data ?? []).filter((n) => {
    if (!searchQ) return true
    const q = searchQ.toLowerCase()
    return (
      n.text.toLowerCase().includes(q) ||
      n.tags.some((tag) => tag.toLowerCase().includes(q))
    )
  })

  const handleCreate = (text: string, tags: string[], description: string) => {
    create.mutate({ text, tags, description })
    setNewOpen(false)
  }

  const handleEdit = (text: string, tags: string[], description: string) => {
    if (!editItem) return
    update.mutate({ id: editItem.id, text, tags, description })
    setEditItem(null)
  }

  if (isLoading) return <MovimientosSkeleton />

  return (
    <div style={{ padding: '14px 18px 24px', display: 'grid', gap: 14 }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center' }}>
        <div className="cap" style={{ flex: 1 }}>Notas</div>
        <button onClick={() => setNewOpen(true)} style={ghostBtn}>+ Nueva</button>
      </div>

      {/* Search */}
      <input
        type="search"
        placeholder="Buscar notas…"
        value={searchQ}
        onChange={(e) => setSearchQ(e.target.value)}
        style={inputStyle}
      />

      {/* List */}
      {filtered.length === 0 && (
        <EmptyState>{searchQ ? 'Sin resultados.' : 'Sin notas aún. ¡Escribí algo!'}</EmptyState>
      )}

      {filtered.map((n) => (
        <Card key={n.id}>
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8 }}>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 14, fontWeight: 500, whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>{n.text}</div>
              {n.description && (
                <div style={{ fontSize: 13, color: 'var(--color-sage)', whiteSpace: 'pre-wrap', wordBreak: 'break-word', marginTop: 4 }}>{n.description}</div>
              )}
              {n.tags.length > 0 && (
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 8 }}>
                  {n.tags.map((tag) => (
                    <span
                      key={tag}
                      style={{
                        fontSize: 11,
                        padding: '2px 8px',
                        borderRadius: 9999,
                        background: 'var(--color-mist)',
                        color: 'var(--color-sage)',
                        fontWeight: 500,
                      }}
                    >
                      {tag}
                    </span>
                  ))}
                </div>
              )}
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 6 }}>
                <span style={{ fontSize: 11, color: 'var(--color-sage)' }}>{n.created_at.slice(0, 10)}</span>
                {me?.id === n.user_id && <ShareBadge shared={n.shared} count={n.share_count} />}
              </div>
            </div>
            <CardActions
              onShare={me?.id === n.user_id ? () => setShareItem(n) : undefined}
              onEdit={() => setEditItem(n)}
              onDelete={me?.id === n.user_id ? () => setDeleteItem(n) : undefined}
            />
          </div>
        </Card>
      ))}

      {/* New modal */}
      <NotaModal
        open={newOpen}
        onClose={() => setNewOpen(false)}
        title="Nueva nota"
        onSubmit={handleCreate}
      />

      {/* Edit modal */}
      <NotaModal
        key={editItem ? `n-${editItem.id}` : 'n-edit'}
        open={editItem !== null}
        onClose={() => setEditItem(null)}
        title="Editar nota"
        initial={editItem ? { text: editItem.text, tags: editItem.tags, description: editItem.description ?? undefined } : undefined}
        onSubmit={handleEdit}
      />

      {/* Share sheet */}
      <ShareSheet
        open={shareItem !== null}
        onClose={() => setShareItem(null)}
        entity="notas"
        id={shareItem?.id ?? null}
      />

      {/* Delete confirm */}
      <ConfirmDialog
        open={deleteItem !== null}
        onOpenChange={(o) => { if (!o) setDeleteItem(null) }}
        title="¿Borrar esta nota?"
        description={deleteItem ? `Se eliminará la nota "${deleteItem.text.slice(0, 40)}…".` : ''}
        onConfirm={() => {
          if (deleteItem) remove.mutate(deleteItem.id)
          setDeleteItem(null)
        }}
      />
    </div>
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
