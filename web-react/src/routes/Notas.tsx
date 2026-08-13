import { useState, useEffect } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useNotas, useNotasMutations } from '../hooks/useNotas'
import { useMe } from '../hooks/useMe'
import { useHouseholdMembers } from '../hooks/useShare'
import { type Nota, type HouseholdMember } from '../lib/types'
import Modal from '../components/ui/Modal'
import ConfirmDialog from '../components/ui/ConfirmDialog'
import EmptyState from '../components/ui/EmptyState'
import ShareSheet from '../components/ui/ShareSheet'
import ShareBadge from '../components/ui/ShareBadge'
import CardActions from '../components/ui/CardActions'
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
    const tags = data.tags.split(',').map((t) => t.trim()).filter(Boolean)
    onSubmit(data.text, tags, (data.description ?? '').trim())
    reset()
  }

  return (
    <Modal open={open} onClose={() => { onClose(); reset() }} title={title}>
      <form onSubmit={handleSubmit(submit)} style={{ display: 'grid', gap: 12 }}>
        <div>
          <input {...register('text')} placeholder="Título de la nota…" autoFocus style={{ ...inputStyle, border: '1.6px solid var(--color-obsidian-ink)', fontWeight: 500 }} />
          {errors.text && <span style={errorStyle}>{errors.text.message}</span>}
        </div>

        <label style={labelStyle}>
          Descripción (opcional)
          <textarea {...register('description')} placeholder="Detalle, contenido más largo…" rows={5} style={{ ...inputStyle, resize: 'vertical' }} />
        </label>

        <label style={labelStyle}>
          Etiquetas (opcional, separadas por coma)
          <input {...register('tags')} placeholder="idea, pendiente, personal…" style={inputStyle} />
        </label>

        <button type="submit" style={solidCta}>Guardar</button>
      </form>
    </Modal>
  )
}

export default function Notas() {
  const [searchQ, setSearchQ] = useState('')
  const [tagFilter, setTagFilter] = useState<string | null>(null)
  const { data, isLoading } = useNotas()
  const { create, update, remove } = useNotasMutations()
  const { data: me } = useMe()
  const { data: members } = useHouseholdMembers()

  const [newOpen, setNewOpen] = useState(false)
  const [editItem, setEditItem] = useState<Nota | null>(null)
  const [deleteItem, setDeleteItem] = useState<Nota | null>(null)
  const [shareItem, setShareItem] = useState<Nota | null>(null)

  const memberById = new Map<number, HouseholdMember>((members ?? []).map((m) => [m.id, m]))
  const notas = data ?? []
  const allTags = [...new Set(notas.flatMap((n) => n.tags))]

  const filtered = notas.filter((n) => {
    if (tagFilter && !n.tags.includes(tagFilter)) return false
    if (!searchQ) return true
    const q = searchQ.toLowerCase()
    return n.text.toLowerCase().includes(q) || (n.description ?? '').toLowerCase().includes(q) || n.tags.some((t) => t.toLowerCase().includes(q))
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
    <div style={{ padding: '10px 18px 24px' }}>
      {/* Título */}
      <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between' }}>
        <div style={pageTitle}>Notas</div>
        <button onClick={() => setNewOpen(true)} style={solidPill}><i className="ti ti-plus" aria-hidden /> Nueva</button>
      </div>

      {/* Buscador */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 9, border: '1px solid var(--color-mist)', borderRadius: 12, padding: '10px 13px', margin: '14px 0 0' }}>
        <i className="ti ti-search" style={{ fontSize: 16, color: 'var(--color-sage)' }} aria-hidden />
        <input
          type="search"
          placeholder="Buscar en notas"
          value={searchQ}
          onChange={(e) => setSearchQ(e.target.value)}
          style={{ flex: 1, border: 'none', background: 'transparent', fontSize: 13, color: 'var(--color-obsidian-ink)', outline: 'none', padding: 0, minWidth: 0 }}
        />
      </div>

      {/* Filtro por etiqueta */}
      {allTags.length > 0 && (
        <div style={{ display: 'flex', gap: 7, padding: '14px 0', overflowX: 'auto' }}>
          <button onClick={() => setTagFilter(null)} style={chip(tagFilter === null)}>Todas</button>
          {allTags.map((t) => (
            <button key={t} onClick={() => setTagFilter(t)} style={chip(tagFilter === t)}>{t}</button>
          ))}
        </div>
      )}

      {/* Lista (masonry 2 columnas) */}
      {filtered.length === 0 ? (
        <div style={{ marginTop: 8 }}>
          <EmptyState>{searchQ || tagFilter ? 'Sin resultados.' : 'Sin notas aún. ¡Escribí algo!'}</EmptyState>
        </div>
      ) : (
        <div style={{ columns: 2, columnGap: 10, marginTop: allTags.length > 0 ? 0 : 14 }}>
          {filtered.map((n) => {
            const owner = memberById.get(n.user_id)
            const isOwner = me?.id === n.user_id
            return (
              <div
                key={n.id}
                style={{ breakInside: 'avoid', display: 'inline-block', width: '100%', marginBottom: 10, border: '1px solid var(--color-mist)', borderRadius: 14, padding: 13, boxSizing: 'border-box' }}
              >
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: 6 }}>
                  <div style={{ flex: 1, fontFamily: 'var(--font-serif)', fontWeight: 600, fontSize: 13.5, lineHeight: 1.3, color: 'var(--color-obsidian-ink)', wordBreak: 'break-word' }}>{n.text}</div>
                  <CardActions
                    onEdit={() => setEditItem(n)}
                    onShare={isOwner ? () => setShareItem(n) : undefined}
                    onDelete={isOwner ? () => setDeleteItem(n) : undefined}
                  />
                </div>
                {n.description && (
                  <div style={{ fontSize: 11.5, lineHeight: 1.45, color: 'var(--color-sage)', marginTop: 6, wordBreak: 'break-word', display: '-webkit-box', WebkitLineClamp: 4, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>{n.description}</div>
                )}
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 10, flexWrap: 'wrap' }}>
                  {n.tags.map((tag) => (
                    <span key={tag} style={{ fontSize: 10, fontWeight: 500, color: 'var(--color-sage)' }}>{tag}</span>
                  ))}
                  {isOwner ? <ShareBadge shared={n.shared} count={n.share_count} /> : owner && <MemberDot member={owner} />}
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* New modal */}
      <NotaModal open={newOpen} onClose={() => setNewOpen(false)} title="Nueva nota" onSubmit={handleCreate} />

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
      <ShareSheet open={shareItem !== null} onClose={() => setShareItem(null)} entity="notas" id={shareItem?.id ?? null} />

      {/* Delete confirm */}
      <ConfirmDialog
        open={deleteItem !== null}
        onOpenChange={(o) => { if (!o) setDeleteItem(null) }}
        title="¿Borrar esta nota?"
        description={deleteItem ? `Se eliminará la nota "${deleteItem.text.slice(0, 40)}…".` : ''}
        onConfirm={() => { if (deleteItem) remove.mutate(deleteItem.id); setDeleteItem(null) }}
      />
    </div>
  )
}

function MemberDot({ member }: { member: HouseholdMember }) {
  return (
    <span
      title={member.name}
      style={{
        width: 15, height: 15, borderRadius: '50%', flexShrink: 0,
        background: member.color || 'rgba(43,238,75,0.22)', color: 'var(--voltage-on-dark)',
        fontSize: 8, fontWeight: 600, display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
      }}
    >
      {member.name.slice(0, 1).toUpperCase()}
    </span>
  )
}

const pageTitle: React.CSSProperties = { fontFamily: 'var(--font-serif)', fontWeight: 600, fontSize: 30, lineHeight: 1.05, color: 'var(--color-obsidian-ink)' }
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
function chip(active: boolean): React.CSSProperties {
  return {
    flex: 'none', whiteSpace: 'nowrap',
    fontSize: 11.5, fontWeight: 600, padding: '7px 12px', borderRadius: 9999, cursor: 'pointer',
    border: active ? '1px solid var(--color-voltage)' : '1px solid var(--color-mist)',
    background: active ? 'var(--color-voltage)' : 'transparent',
    color: active ? 'var(--voltage-on-dark)' : 'var(--color-obsidian-ink)',
  }
}
