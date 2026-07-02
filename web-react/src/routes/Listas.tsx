import { useState } from 'react'
import { useListas, useListaTemplates, useListasMutations } from '../hooks/useListas'
import { type Lista } from '../lib/types'
import Card from '../components/ui/Card'
import Modal from '../components/ui/Modal'
import ConfirmDialog from '../components/ui/ConfirmDialog'
import EmptyState from '../components/ui/EmptyState'
import ShareSheet from '../components/ui/ShareSheet'
import ShareBadge from '../components/ui/ShareBadge'
import { MovimientosSkeleton } from '../components/ui/skeletons'

function NuevaListaModal({
  open,
  onClose,
  onSubmit,
}: {
  open: boolean
  onClose: () => void
  onSubmit: (name: string) => void
}) {
  const [name, setName] = useState('')

  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!name.trim()) return
    onSubmit(name.trim())
    setName('')
  }

  return (
    <Modal open={open} onClose={() => { onClose(); setName('') }} title="Nueva lista">
      <form onSubmit={submit} style={{ display: 'grid', gap: 12 }}>
        <input
          autoFocus
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Nombre de la lista…"
          style={inputStyle}
        />
        <button type="submit" disabled={!name.trim()} style={ctaBtn}>Crear</button>
      </form>
    </Modal>
  )
}

function AddItemModal({
  open,
  onClose,
  onSubmit,
}: {
  open: boolean
  onClose: () => void
  onSubmit: (text: string) => void
}) {
  const [text, setText] = useState('')

  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!text.trim()) return
    onSubmit(text.trim())
    setText('')
  }

  return (
    <Modal open={open} onClose={() => { onClose(); setText('') }} title="Agregar ítem">
      <form onSubmit={submit} style={{ display: 'grid', gap: 12 }}>
        <input
          autoFocus
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="p. ej. 2 kg arroz, leche…"
          style={inputStyle}
        />
        <button type="submit" disabled={!text.trim()} style={ctaBtn}>Agregar</button>
      </form>
    </Modal>
  )
}

function ListaCard({
  lista,
  onAddItem,
  onToggleItem,
  onDeleteItem,
  onClearDone,
  onBuyAll,
  onDeleteLista,
  onShare,
}: {
  lista: Lista
  onAddItem: (listaId: number) => void
  onToggleItem: (iid: number) => void
  onDeleteItem: (iid: number) => void
  onClearDone: (listaId: number) => void
  onBuyAll: (listaId: number) => void
  onDeleteLista: (lista: Lista) => void
  onShare: (lista: Lista) => void
}) {
  const [expanded, setExpanded] = useState(true)
  const doneCount = lista.items.filter((i) => i.done === 1).length
  const isOwner = lista.is_owner !== 0  // backend manda 1/0; undefined → tratamos como propia

  return (
    <Card>
      {/* Lista header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: expanded ? 12 : 0 }}>
        {lista.icon && <span style={{ fontSize: 18 }}>{lista.icon}</span>}
        <button
          onClick={() => setExpanded((x) => !x)}
          style={{ background: 'none', border: 'none', cursor: 'pointer', flex: 1, textAlign: 'left', padding: 0 }}
        >
          <span style={{ fontSize: 15, fontWeight: 600 }}>{lista.name}</span>
          <span style={{ fontSize: 12, color: 'var(--color-sage)', marginLeft: 8 }}>
            {lista.pend} pendiente{lista.pend === 1 ? '' : 's'} / {lista.total}
          </span>
          {isOwner && (
            <span style={{ marginLeft: 8 }}><ShareBadge shared={lista.shared} count={lista.share_count} /></span>
          )}
        </button>
        <div style={{ display: 'flex', gap: 6 }}>
          <button
            onClick={() => onAddItem(lista.id)}
            title="Agregar ítem"
            style={iconBtn}
          >
            <i className="ti ti-plus" aria-hidden />
          </button>
          {doneCount > 0 && (
            <button
              onClick={() => onClearDone(lista.id)}
              title="Borrar completados"
              style={iconBtn}
            >
              <i className="ti ti-eraser" aria-hidden />
            </button>
          )}
          {lista.pend > 0 && (
            <button
              onClick={() => onBuyAll(lista.id)}
              title="Marcar todo como comprado"
              style={iconBtn}
            >
              <i className="ti ti-shopping-cart-check" aria-hidden />
            </button>
          )}
          {isOwner && (
            <button
              onClick={() => onShare(lista)}
              title="Compartir lista"
              style={iconBtn}
            >
              <i className="ti ti-users" aria-hidden />
            </button>
          )}
          {isOwner && (
            <button
              onClick={() => onDeleteLista(lista)}
              title="Eliminar lista"
              style={{ ...iconBtn, color: 'var(--color-error)' }}
            >
              <i className="ti ti-trash" aria-hidden />
            </button>
          )}
        </div>
      </div>

      {/* Items */}
      {expanded && (
        <div style={{ display: 'grid', gap: 6 }}>
          {lista.items.length === 0 && (
            <div style={{ fontSize: 13, color: 'var(--color-sage)', fontStyle: 'italic', padding: '4px 0' }}>
              Lista vacía — agregá un ítem
            </div>
          )}
          {lista.items.map((item) => (
            <div
              key={item.id}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 10,
                padding: '6px 0',
                borderBottom: '1px solid var(--color-mist)',
                opacity: item.done === 1 ? 0.55 : 1,
              }}
            >
              {/* Checkbox */}
              <button
                onClick={() => onToggleItem(item.id)}
                aria-label={item.done === 1 ? 'Desmarcar' : 'Marcar como comprado'}
                style={{
                  width: 20,
                  height: 20,
                  borderRadius: 5,
                  border: `2px solid ${item.done === 1 ? 'var(--color-voltage)' : 'var(--color-mist)'}`,
                  background: item.done === 1 ? 'var(--color-voltage)' : 'transparent',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  cursor: 'pointer',
                  flexShrink: 0,
                }}
              >
                {item.done === 1 && (
                  <i className="ti ti-check" style={{ fontSize: 12, color: 'var(--voltage-on-dark)' }} aria-hidden />
                )}
              </button>

              {/* Text */}
              <span style={{
                flex: 1,
                fontSize: 14,
                textDecoration: item.done === 1 ? 'line-through' : 'none',
              }}>
                {item.qty != null && (
                  <span style={{ fontWeight: 600 }}>
                    {item.qty}{item.unit ? ` ${item.unit}` : ''}{' '}
                  </span>
                )}
                {item.text}
              </span>

              {/* Delete */}
              <button
                onClick={() => onDeleteItem(item.id)}
                aria-label={`Borrar ${item.text}`}
                style={{ ...iconBtn, color: 'var(--color-mist)' }}
              >
                <i className="ti ti-x" aria-hidden />
              </button>
            </div>
          ))}
        </div>
      )}
    </Card>
  )
}

export default function Listas() {
  const { data, isLoading } = useListas()
  const templates = useListaTemplates()
  const { createLista, deleteLista, addItem, toggleItem, deleteItem, clearDone, buyAll, useTemplate } =
    useListasMutations()

  const [newListaOpen, setNewListaOpen] = useState(false)
  const [addItemForLista, setAddItemForLista] = useState<number | null>(null)
  const [deleteConfirm, setDeleteConfirm] = useState<Lista | null>(null)
  const [templateOpen, setTemplateOpen] = useState(false)
  const [shareLista, setShareLista] = useState<Lista | null>(null)

  if (isLoading) return <MovimientosSkeleton />

  const listas = data ?? []
  const templateList = templates.data ?? []

  return (
    <div style={{ padding: '14px 18px 24px', display: 'grid', gap: 14 }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <div className="cap" style={{ flex: 1 }}>Listas</div>
        {templateList.length > 0 && (
          <button onClick={() => setTemplateOpen(true)} style={ghostBtn}>
            <i className="ti ti-template" aria-hidden /> Plantilla
          </button>
        )}
        <button onClick={() => setNewListaOpen(true)} style={ghostBtn}>+ Nueva</button>
      </div>

      {listas.length === 0 && (
        <EmptyState>Sin listas aún. ¡Creá una!</EmptyState>
      )}

      {listas.map((lista) => (
        <ListaCard
          key={lista.id}
          lista={lista}
          onAddItem={(id) => setAddItemForLista(id)}
          onToggleItem={(iid) => toggleItem.mutate(iid)}
          onDeleteItem={(iid) => deleteItem.mutate(iid)}
          onClearDone={(id) => clearDone.mutate(id)}
          onBuyAll={(id) => buyAll.mutate(id)}
          onDeleteLista={(l) => setDeleteConfirm(l)}
          onShare={(l) => setShareLista(l)}
        />
      ))}

      {/* Share sheet */}
      <ShareSheet
        open={shareLista !== null}
        onClose={() => setShareLista(null)}
        entity="lists"
        id={shareLista?.id ?? null}
      />

      {/* Nueva lista modal */}
      <NuevaListaModal
        open={newListaOpen}
        onClose={() => setNewListaOpen(false)}
        onSubmit={(name) => {
          createLista.mutate(name)
          setNewListaOpen(false)
        }}
      />

      {/* Add item modal */}
      <AddItemModal
        open={addItemForLista !== null}
        onClose={() => setAddItemForLista(null)}
        onSubmit={(text) => {
          if (addItemForLista !== null) addItem.mutate({ listaId: addItemForLista, text })
          setAddItemForLista(null)
        }}
      />

      {/* Delete lista confirm */}
      <ConfirmDialog
        open={deleteConfirm !== null}
        onOpenChange={(o) => { if (!o) setDeleteConfirm(null) }}
        title="¿Eliminar esta lista?"
        description={deleteConfirm ? `Se eliminará "${deleteConfirm.name}" y todos sus ítems.` : ''}
        onConfirm={() => {
          if (deleteConfirm) deleteLista.mutate(deleteConfirm.id)
          setDeleteConfirm(null)
        }}
      />

      {/* Templates modal */}
      {templateList.length > 0 && (
        <Modal open={templateOpen} onClose={() => setTemplateOpen(false)} title="Usar plantilla">
          <div style={{ display: 'grid', gap: 10 }}>
            {templateList.map((t) => (
              <button
                key={t.id}
                onClick={() => {
                  useTemplate.mutate({ name: t.name })
                  setTemplateOpen(false)
                }}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 10,
                  padding: '12px 14px',
                  background: 'var(--color-linen)',
                  border: '1px solid var(--color-mist)',
                  borderRadius: 10,
                  cursor: 'pointer',
                  textAlign: 'left',
                }}
              >
                {t.icon && <span style={{ fontSize: 18 }}>{t.icon}</span>}
                <span style={{ flex: 1, fontSize: 14, fontWeight: 500 }}>{t.name}</span>
                <span style={{ fontSize: 12, color: 'var(--color-sage)' }}>{t.total} ítems</span>
              </button>
            ))}
          </div>
        </Modal>
      )}
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
const iconBtn: React.CSSProperties = {
  background: 'none',
  border: 'none',
  cursor: 'pointer',
  color: 'var(--color-sage)',
  fontSize: 16,
  padding: 2,
  display: 'flex',
  alignItems: 'center',
}
