import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { useCategories, useCategoryMutations } from '../hooks/useCategories'
import { type Category } from '../lib/types'
import Card from '../components/ui/Card'
import EmptyState from '../components/ui/EmptyState'
import Modal from '../components/ui/Modal'
import ConfirmDialog from '../components/ui/ConfirmDialog'
import CardActions from '../components/ui/CardActions'

interface CatForm { name: string }

function CategoryFormModal({ open, onClose, initial, onSubmit, title }: {
  open: boolean
  onClose: () => void
  initial?: CatForm
  onSubmit: (data: CatForm) => void
  title: string
}) {
  const { register, handleSubmit, reset } = useForm<CatForm>({
    defaultValues: initial ?? { name: '' },
  })
  const submit = (data: CatForm) => { onSubmit(data); reset() }
  return (
    <Modal open={open} onClose={() => { onClose(); reset() }} title={title}>
      <form onSubmit={handleSubmit(submit)} style={{ display: 'grid', gap: 12 }}>
        <input
          {...register('name', { required: true })}
          placeholder="Nombre de la categoría"
          style={inputStyle}
        />
        <button type="submit" style={ctaBtn}>Guardar</button>
      </form>
    </Modal>
  )
}

export default function Categorias() {
  const { data } = useCategories()
  const { create, update, remove } = useCategoryMutations()

  const [createOpen, setCreateOpen] = useState(false)
  const [editCat, setEditCat] = useState<Category | null>(null)
  const [deleteCat, setDeleteCat] = useState<Category | null>(null)

  return (
    <div style={{ padding: '14px 18px 24px', display: 'grid', gap: 10 }}>
      <div style={{ display: 'flex', alignItems: 'center' }}>
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
              {/* Name left, actions right */}
              <span style={{ fontSize: 14, flex: 1 }}>{c.name}</span>
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
        initial={editCat ? { name: editCat.name } : undefined}
        title="Editar categoría"
        onSubmit={(data) => {
          if (editCat) update.mutate({ id: editCat.id, name: data.name })
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
