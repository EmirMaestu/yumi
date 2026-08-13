import { useState } from 'react'
import { useListas, useListaTemplates, useListasMutations } from '../hooks/useListas'
import { type Lista } from '../lib/types'
import Card from '../components/ui/Card'
import Modal from '../components/ui/Modal'
import Sheet from '../components/ui/Sheet'
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
          style={{ ...inputStyle, border: '1.6px solid var(--color-obsidian-ink)', fontWeight: 500 }}
        />
        <button type="submit" disabled={!name.trim()} style={solidCta}>Crear</button>
      </form>
    </Modal>
  )
}

function InlineAdd({ onAdd }: { onAdd: (text: string) => void }) {
  const [text, setText] = useState('')
  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!text.trim()) return
    onAdd(text.trim())
    setText('')
  }
  return (
    <form onSubmit={submit} style={{ display: 'flex', alignItems: 'center', gap: 10, border: '1.6px solid var(--color-obsidian-ink)', borderRadius: 14, padding: '11px 14px', marginBottom: 14 }}>
      <button type="submit" aria-label="Agregar ítem" style={{ background: 'none', border: 'none', padding: 0, cursor: 'pointer', color: 'var(--color-obsidian-ink)', display: 'flex' }}>
        <i className="ti ti-plus" style={{ fontSize: 18 }} aria-hidden />
      </button>
      <input
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="Agregar ítem…"
        style={{ flex: 1, border: 'none', background: 'transparent', fontSize: 13.5, color: 'var(--color-obsidian-ink)', outline: 'none', padding: 0, minWidth: 0 }}
      />
      <i className="ti ti-microphone" style={{ fontSize: 17, color: 'var(--color-sage)', flexShrink: 0 }} aria-hidden />
    </form>
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
  onAddItem: (listaId: number, text: string) => void
  onToggleItem: (iid: number) => void
  onDeleteItem: (iid: number) => void
  onClearDone: (listaId: number) => void
  onBuyAll: (listaId: number) => void
  onDeleteLista: (lista: Lista) => void
  onShare: (lista: Lista) => void
}) {
  const doneCount = lista.items.filter((i) => i.done === 1).length
  const isOwner = lista.is_owner !== 0

  return (
    <Card style={{ padding: 15, marginBottom: 14 }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', marginBottom: 13 }}>
        <div style={{ minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
            {lista.icon && <span style={{ fontSize: 20 }}>{lista.icon}</span>}
            <span style={{ fontFamily: 'var(--font-serif)', fontWeight: 600, fontSize: 22, color: 'var(--color-obsidian-ink)' }}>{lista.name}</span>
          </div>
          <div style={{ fontSize: 12, color: 'var(--color-sage)', marginTop: 2, display: 'flex', alignItems: 'center', gap: 8 }}>
            <span>{lista.total} ítem{lista.total === 1 ? '' : 's'} · {doneCount} tildado{doneCount === 1 ? '' : 's'}</span>
            {isOwner && <ShareBadge shared={lista.shared} count={lista.share_count} />}
          </div>
        </div>
        <div style={{ display: 'flex', gap: 4 }}>
          {isOwner && (
            <button onClick={() => onShare(lista)} title="Compartir lista" style={iconBtn}><i className="ti ti-users" aria-hidden /></button>
          )}
          {isOwner && (
            <button onClick={() => onDeleteLista(lista)} title="Eliminar lista" style={{ ...iconBtn, color: 'var(--color-error)' }}><i className="ti ti-trash" aria-hidden /></button>
          )}
        </div>
      </div>

      {/* Agregar ítem (fijo arriba) */}
      <InlineAdd onAdd={(t) => onAddItem(lista.id, t)} />

      {/* Ítems */}
      {lista.items.length === 0 ? (
        <div style={{ fontSize: 13, color: 'var(--color-sage)', fontStyle: 'italic', padding: '4px 0' }}>Lista vacía — agregá un ítem</div>
      ) : (
        <div>
          {lista.items.map((item, idx) => (
            <div
              key={item.id}
              style={{
                display: 'flex', alignItems: 'center', gap: 11, padding: '11px 0',
                borderBottom: idx < lista.items.length - 1 ? '1px solid var(--color-mist)' : 'none',
                opacity: item.done === 1 ? 0.5 : 1,
              }}
            >
              <button
                onClick={() => onToggleItem(item.id)}
                aria-label={item.done === 1 ? 'Desmarcar' : 'Marcar como comprado'}
                style={{
                  width: 18, height: 18, borderRadius: '50%', flexShrink: 0,
                  border: `1.6px solid ${item.done === 1 ? 'var(--color-voltage)' : 'var(--color-mist)'}`,
                  background: item.done === 1 ? 'var(--color-voltage)' : 'transparent',
                  display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer',
                }}
              >
                {item.done === 1 && <i className="ti ti-check" style={{ fontSize: 11, color: 'var(--voltage-on-dark)' }} aria-hidden />}
              </button>
              <span style={{ flex: 1, fontSize: 13.5, fontWeight: 500, textDecoration: item.done === 1 ? 'line-through' : 'none', color: 'var(--color-obsidian-ink)' }}>
                {item.qty != null && <span style={{ fontWeight: 600 }}>{item.qty}{item.unit ? ` ${item.unit}` : ''} </span>}
                {item.text}
              </span>
              <button onClick={() => onDeleteItem(item.id)} aria-label={`Borrar ${item.text}`} style={{ ...iconBtn, color: 'var(--color-mist)' }}>
                <i className="ti ti-x" aria-hidden />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Acciones */}
      {(doneCount > 0 || lista.pend > 0) && (
        <div style={{ display: 'flex', gap: 8, marginTop: 14, flexWrap: 'wrap' }}>
          {doneCount > 0 && <button onClick={() => onClearDone(lista.id)} style={ghostChip}>Vaciar tildados</button>}
          {lista.pend > 0 && <button onClick={() => onBuyAll(lista.id)} style={ghostChip}>Comprar todo</button>}
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
  const [deleteConfirm, setDeleteConfirm] = useState<Lista | null>(null)
  const [templateOpen, setTemplateOpen] = useState(false)
  const [shareLista, setShareLista] = useState<Lista | null>(null)

  if (isLoading) return <MovimientosSkeleton />

  const listas = data ?? []
  const templateList = templates.data ?? []

  return (
    <div style={{ padding: '10px 18px 24px' }}>
      {/* Título */}
      <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', marginBottom: 16 }}>
        <div>
          <div style={pageTitle}>Listas</div>
          <div style={pageSub}>{listas.length} lista{listas.length === 1 ? '' : 's'}</div>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          {templateList.length > 0 && (
            <button onClick={() => setTemplateOpen(true)} style={softChip}>Plantillas</button>
          )}
          <button onClick={() => setNewListaOpen(true)} style={solidPill}><i className="ti ti-plus" aria-hidden /> Nueva</button>
        </div>
      </div>

      {listas.length === 0 && <EmptyState>Sin listas aún. ¡Creá una!</EmptyState>}

      {listas.map((lista) => (
        <ListaCard
          key={lista.id}
          lista={lista}
          onAddItem={(id, text) => addItem.mutate({ listaId: id, text })}
          onToggleItem={(iid) => toggleItem.mutate(iid)}
          onDeleteItem={(iid) => deleteItem.mutate(iid)}
          onClearDone={(id) => clearDone.mutate(id)}
          onBuyAll={(id) => buyAll.mutate(id)}
          onDeleteLista={(l) => setDeleteConfirm(l)}
          onShare={(l) => setShareLista(l)}
        />
      ))}

      {/* Share sheet */}
      <ShareSheet open={shareLista !== null} onClose={() => setShareLista(null)} entity="lists" id={shareLista?.id ?? null} />

      {/* Nueva lista modal */}
      <NuevaListaModal
        open={newListaOpen}
        onClose={() => setNewListaOpen(false)}
        onSubmit={(name) => { createLista.mutate(name); setNewListaOpen(false) }}
      />

      {/* Delete lista confirm */}
      <ConfirmDialog
        open={deleteConfirm !== null}
        onOpenChange={(o) => { if (!o) setDeleteConfirm(null) }}
        title="¿Eliminar esta lista?"
        description={deleteConfirm ? `Se eliminará "${deleteConfirm.name}" y todos sus ítems.` : ''}
        onConfirm={() => { if (deleteConfirm) deleteLista.mutate(deleteConfirm.id); setDeleteConfirm(null) }}
      />

      {/* Plantillas drawer */}
      {templateList.length > 0 && (
        <Sheet open={templateOpen} onClose={() => setTemplateOpen(false)} title="Plantillas">
          <div style={{ fontSize: 12, lineHeight: 1.4, color: 'var(--color-sage)', marginBottom: 14 }}>
            Sumá un set de ítems de una vez. No borra lo que ya tenés.
          </div>
          <div style={{ display: 'grid', gap: 9 }}>
            {templateList.map((t) => (
              <div key={t.id} style={{ display: 'flex', alignItems: 'center', gap: 12, border: '1px solid var(--color-mist)', borderRadius: 13, padding: '13px 14px' }}>
                {t.icon && <span style={{ fontSize: 18 }}>{t.icon}</span>}
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 13.5, fontWeight: 600, color: 'var(--color-obsidian-ink)' }}>{t.name}</div>
                  <div style={{ fontSize: 11, color: 'var(--color-sage)', marginTop: 2 }}>{t.total} ítems</div>
                </div>
                <button
                  onClick={() => { useTemplate.mutate({ name: t.name }); setTemplateOpen(false) }}
                  style={solidChipSm}
                >
                  Sumar
                </button>
              </div>
            ))}
          </div>
        </Sheet>
      )}
    </div>
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
const solidCta: React.CSSProperties = {
  background: 'var(--color-voltage)', color: 'var(--voltage-on-dark)', border: 'none',
  borderRadius: 12, padding: '14px', fontWeight: 600, fontSize: 14, cursor: 'pointer',
}
const solidPill: React.CSSProperties = {
  display: 'inline-flex', alignItems: 'center', gap: 5,
  background: 'var(--color-voltage)', color: 'var(--voltage-on-dark)', border: 'none',
  borderRadius: 9999, padding: '9px 15px', fontSize: 12.5, fontWeight: 600, cursor: 'pointer',
}
const softChip: React.CSSProperties = {
  background: 'rgba(43,238,75,0.14)', color: 'var(--color-obsidian-ink)', border: 'none',
  borderRadius: 9999, padding: '9px 14px', fontSize: 12, fontWeight: 600, cursor: 'pointer',
}
const solidChipSm: React.CSSProperties = {
  background: 'var(--color-voltage)', color: 'var(--voltage-on-dark)', border: 'none',
  borderRadius: 9999, padding: '7px 14px', fontSize: 11.5, fontWeight: 600, cursor: 'pointer', flexShrink: 0,
}
const ghostChip: React.CSSProperties = {
  background: 'transparent', color: 'var(--color-sage)', border: '1px solid var(--color-mist)',
  borderRadius: 9999, padding: '7px 12px', fontSize: 11.5, fontWeight: 600, cursor: 'pointer',
}
const iconBtn: React.CSSProperties = {
  background: 'none', border: 'none', cursor: 'pointer', color: 'var(--color-sage)', fontSize: 16, padding: 3, display: 'flex', alignItems: 'center',
}
