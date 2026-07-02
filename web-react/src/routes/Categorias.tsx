import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { useCategories, useCategoryMutations } from '../hooks/useCategories'
import { type Category } from '../lib/types'
import { PALETTE } from '../lib/palette'
import Card from '../components/ui/Card'
import BackButton from '../components/ui/BackButton'
import EmptyState from '../components/ui/EmptyState'
import Modal from '../components/ui/Modal'
import ConfirmDialog from '../components/ui/ConfirmDialog'
import CardActions from '../components/ui/CardActions'
import { CategoriasSkeleton } from '../components/ui/skeletons'

interface CatForm { name: string; color?: string; icon?: string }

function CategoryFormModal({ open, onClose, initial, onSubmit, title }: {
  open: boolean
  onClose: () => void
  initial?: CatForm
  onSubmit: (data: CatForm) => void
  title: string
}) {
  const { register, handleSubmit, reset, watch, setValue, formState: { errors } } = useForm<CatForm>({
    defaultValues: initial ?? { name: '', color: PALETTE[0], icon: '' },
  })
  const color = watch('color')
  const submit = (data: CatForm) => { onSubmit(data); reset() }
  return (
    <Modal open={open} onClose={() => { onClose(); reset() }} title={title}>
      <form onSubmit={handleSubmit(submit)} style={{ display: 'grid', gap: 12 }}>
        <div>
          <input
            {...register('name', { required: 'Requerido' })}
            placeholder="Nombre de la categoría"
            style={inputStyle}
          />
          {errors.name && <span style={errorStyle}>{errors.name.message}</span>}
        </div>
        <input {...register('icon')} placeholder="Emoji (opcional, ej. 🛒)" maxLength={2} style={inputStyle} />
        <div>
          <span style={{ fontSize: 13, color: 'var(--color-sage)' }}>Color</span>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 6 }}>
            {PALETTE.map((c) => (
              <button key={c} type="button" onClick={() => setValue('color', c)} aria-label={`Color ${c}`}
                style={{ width: 26, height: 26, borderRadius: '50%', background: c, cursor: 'pointer', border: color === c ? '2px solid var(--color-obsidian-ink)' : '2px solid transparent' }} />
            ))}
          </div>
        </div>
        <button type="submit" style={ctaBtn}>Guardar</button>
      </form>
    </Modal>
  )
}

export default function Categorias() {
  const { data, isLoading } = useCategories()
  const { create, update, remove } = useCategoryMutations()

  const [createOpen, setCreateOpen] = useState(false)
  const [editCat, setEditCat] = useState<Category | null>(null)
  const [deleteCat, setDeleteCat] = useState<Category | null>(null)

  if (isLoading) return <CategoriasSkeleton />

  return (
    <div style={{ padding: '14px 18px 24px', display: 'grid', gap: 10 }}>
      <div style={{ display: 'flex', alignItems: 'center' }}>
        <BackButton />
        <div className="cap" style={{ flex: 1 }}>Categorías</div>
        <button onClick={() => setCreateOpen(true)} style={ghostBtn}>+ Nueva categoría</button>
      </div>

      {!data || data.length === 0 ? <EmptyState>Sin categorías.</EmptyState> : (
        <Card>
          {data.map((c) => (
            <div
              key={c.id}
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                padding: '10px 0',
                borderBottom: '1px solid var(--color-mist)',
              }}
            >
              {/* Dot de color + emoji + nombre */}
              <span style={{ fontSize: 14, flex: 1, display: 'inline-flex', alignItems: 'center', gap: 7 }}>
                <span style={{ width: 10, height: 10, borderRadius: '50%', background: c.color ?? 'var(--color-mist)', flexShrink: 0 }} />
                {c.icon ? <span>{c.icon}</span> : null}
                {c.name}
              </span>
              <CardActions
                onEdit={() => setEditCat(c)}
                onDelete={() => setDeleteCat(c)}
              />
            </div>
          ))}
        </Card>
      )}

      {/* Create modal */}
      <CategoryFormModal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        title="Nueva categoría"
        onSubmit={(data) => { create.mutate(data); setCreateOpen(false) }}
      />

      {/* Edit modal */}
      <CategoryFormModal
        key={editCat ? `cat-${editCat.id}` : 'cat-edit'}
        open={editCat !== null}
        onClose={() => setEditCat(null)}
        initial={editCat ? { name: editCat.name, color: editCat.color ?? PALETTE[0], icon: editCat.icon ?? '' } : undefined}
        title="Editar categoría"
        onSubmit={(data) => {
          if (editCat) update.mutate({ id: editCat.id, name: data.name, color: data.color, icon: data.icon })
          setEditCat(null)
        }}
      />

      {/* Delete confirm */}
      <ConfirmDialog
        open={deleteCat !== null}
        onOpenChange={(o) => { if (!o) setDeleteCat(null) }}
        title="¿Borrar esta categoría?"
        description={deleteCat ? `Se eliminará "${deleteCat.name}".` : ''}
        onConfirm={() => {
          if (deleteCat) remove.mutate(deleteCat.id)
          setDeleteCat(null)
        }}
      />
    </div>
  )
}

const ghostBtn: React.CSSProperties = {
  background: 'transparent',
  border: '1px solid var(--color-mist)',
  borderRadius: 10,
  padding: '7px 14px',
  fontSize: 13,
  cursor: 'pointer',
}
const ctaBtn: React.CSSProperties = {
  background: 'var(--color-voltage)',
  color: 'var(--voltage-on-dark)',
  border: 'none',
  borderRadius: 10,
  padding: '14px',
  fontWeight: 500,
  cursor: 'pointer',
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
const errorStyle: React.CSSProperties = { fontSize: 12, color: 'var(--color-error)', marginTop: 2 }
