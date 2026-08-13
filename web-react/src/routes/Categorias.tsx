import { type CSSProperties, useMemo, useState } from 'react'
import { useForm } from 'react-hook-form'
import { useNavigate } from 'react-router-dom'
import { useCategories, useCategoryMutations } from '../hooks/useCategories'
import { useOverview } from '../hooks/useOverview'
import { type Category } from '../lib/types'
import { PALETTE } from '../lib/palette'
import { formatMoney } from '../lib/format'
import EmptyState from '../components/ui/EmptyState'
import Sheet from '../components/ui/Sheet'
import ConfirmDialog from '../components/ui/ConfirmDialog'
import { CategoriasSkeleton } from '../components/ui/skeletons'

const EMOJIS = ['🍽', '🍕', '☕', '🍺', '🛒', '🎁', '🏠', '⛽', '🚌', '💊', '👕', '🎬', '✈️', '📱', '💡', '🐶']

// Convierte un hex de la paleta a un rgba tenue para los tintes de fondo
// (funciona igual en claro y oscuro porque el color es de marca, no del tema).
function tint(hex: string | undefined, alpha: number): string {
  if (!hex || !/^#[0-9a-f]{6}$/i.test(hex)) return 'var(--color-mist)'
  const n = parseInt(hex.slice(1), 16)
  return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${alpha})`
}

interface CatForm { name: string }

// Drawer de edición/creación (4c): color + emoji + el gasto del mes para contexto.
function CategoryDrawer({ initial, monthSpend, onSubmit, onDelete }: {
  initial?: Category
  monthSpend: number
  onSubmit: (data: { name: string; color?: string; icon?: string }) => void
  onDelete?: () => void
}) {
  const { register, handleSubmit, formState: { errors } } = useForm<CatForm>({
    defaultValues: { name: initial?.name ?? '' },
  })
  const [color, setColor] = useState<string>(initial?.color ?? PALETTE[0])
  const [icon, setIcon] = useState<string>(initial?.icon ?? '')

  const submit = (data: CatForm) => onSubmit({ name: data.name.trim(), color, icon: icon || undefined })

  return (
    <form onSubmit={handleSubmit(submit)} style={{ display: 'grid', gap: 0 }}>
      {/* Emoji grande + nombre */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <span style={{ ...bigTile, background: tint(color, 0.18) }}>{icon || '🏷️'}</span>
        <div style={{ flex: 1 }}>
          <input
            {...register('name', { required: 'Requerido' })}
            placeholder="Nombre de la categoría"
            autoFocus
            style={nameInput}
          />
          {errors.name && <span style={errorStyle}>{errors.name.message}</span>}
        </div>
      </div>

      {/* Color */}
      <Label>Color</Label>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10 }}>
        {PALETTE.map((c) => (
          <button
            key={c}
            type="button"
            onClick={() => setColor(c)}
            aria-label={`Color ${c}`}
            style={{
              width: 34, height: 34, borderRadius: '50%', background: c, cursor: 'pointer', border: 'none', padding: 0,
              boxShadow: color === c ? '0 0 0 2px var(--color-linen), 0 0 0 4px var(--color-obsidian-ink)' : 'none',
            }}
          />
        ))}
      </div>

      {/* Emoji */}
      <Label>Emoji</Label>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 9 }}>
        {EMOJIS.map((e) => (
          <button
            key={e}
            type="button"
            onClick={() => setIcon((cur) => (cur === e ? '' : e))}
            aria-label={`Emoji ${e}`}
            style={{
              width: 38, height: 38, borderRadius: 11, fontSize: 18, cursor: 'pointer', padding: 0,
              background: icon === e ? tint(color, 0.22) : 'var(--color-mist)',
              border: icon === e ? '1.6px solid var(--color-obsidian-ink)' : '1.6px solid transparent',
            }}
          >
            {e}
          </button>
        ))}
      </div>

      {/* Contexto */}
      <div style={context}>
        {monthSpend > 0
          ? <>Este mes gastaste <b>{formatMoney(monthSpend)}</b> en esta categoría. </>
          : <>Sin gasto este mes en esta categoría. </>}
        {onDelete && <>Si la borrás, sus movimientos pasan a “Sin categoría”.</>}
      </div>

      {/* Acciones */}
      <div style={{ display: 'flex', gap: 9, marginTop: 14 }}>
        {onDelete && (
          <button type="button" onClick={onDelete} style={deleteBtn}>Borrar</button>
        )}
        <button type="submit" style={saveBtn}>Guardar</button>
      </div>
    </form>
  )
}

export default function Categorias() {
  const navigate = useNavigate()
  const { data, isLoading } = useCategories()
  const { data: overview } = useOverview()
  const { create, update, remove } = useCategoryMutations()

  const [mode, setMode] = useState<'new' | Category | null>(null)
  const [deleteCat, setDeleteCat] = useState<Category | null>(null)

  // Gasto del mes por categoría (por nombre) desde el overview.
  const spendByName = useMemo(() => {
    const m = new Map<string, number>()
    for (const c of overview?.por_categoria ?? []) m.set(c.cat, (m.get(c.cat) ?? 0) + c.total)
    return m
  }, [overview])
  const spendOf = (c: Category) => spendByName.get(c.name) ?? 0

  if (isLoading) return <CategoriasSkeleton />

  const cats = data ?? []
  const conGasto = cats.filter((c) => spendOf(c) > 0).length
  const editing = mode && mode !== 'new' ? mode : undefined

  return (
    <div style={{ padding: '14px 18px 24px', display: 'grid', gap: 0 }}>
      {/* Encabezado */}
      <button onClick={() => navigate('/finanzas')} style={backLink}>
        <i className="ti ti-arrow-left" style={{ fontSize: 15 }} aria-hidden /> Resumen
      </button>
      <div className="num-serif" style={{ fontSize: 30, marginTop: 6 }}>Categorías</div>
      <div style={{ fontSize: 12.5, color: 'var(--color-sage)', marginTop: 3 }}>
        {cats.length} categoría{cats.length === 1 ? '' : 's'}
        {conGasto > 0 && ` · ${conGasto} con gasto este mes`}
      </div>

      {cats.length === 0 ? (
        <div style={{ marginTop: 16 }}><EmptyState>Sin categorías.</EmptyState></div>
      ) : (
        <div style={{ marginTop: 16, border: '1px solid var(--color-mist)', borderRadius: 14, overflow: 'hidden' }}>
          {cats.map((c, i) => {
            const spent = spendOf(c)
            return (
              <button
                key={c.id}
                onClick={() => setMode(c)}
                style={{ ...catRow, borderBottom: i < cats.length - 1 ? '1px solid var(--color-mist)' : 'none' }}
              >
                <span style={{ ...emojiTile, background: tint(c.color, 0.18) }}>{c.icon || '🏷️'}</span>
                <span style={{ fontSize: 13.5, fontWeight: 500, color: 'var(--color-obsidian-ink)', flex: 1, textAlign: 'left' }}>{c.name}</span>
                <span style={{ fontSize: 12.5, fontWeight: 600, color: spent > 0 ? 'var(--color-obsidian-ink)' : 'var(--color-sage)' }}>
                  {formatMoney(spent)}
                </span>
              </button>
            )
          })}
        </div>
      )}

      {/* Nueva categoría */}
      <button onClick={() => setMode('new')} style={newRow}>+ Nueva categoría</button>

      {/* Drawer crear / editar */}
      <Sheet open={mode !== null} onClose={() => setMode(null)} title={editing ? 'Editar categoría' : 'Nueva categoría'}>
        {mode !== null && (
          <CategoryDrawer
            key={editing ? `cat-${editing.id}` : 'cat-new'}
            initial={editing}
            monthSpend={editing ? spendOf(editing) : 0}
            onSubmit={(d) => {
              if (editing) update.mutate({ id: editing.id, ...d })
              else create.mutate(d)
              setMode(null)
            }}
            onDelete={editing ? () => { setDeleteCat(editing); setMode(null) } : undefined}
          />
        )}
      </Sheet>

      {/* Confirmar borrado */}
      <ConfirmDialog
        open={deleteCat !== null}
        onOpenChange={(o) => { if (!o) setDeleteCat(null) }}
        title="¿Borrar esta categoría?"
        description={deleteCat ? `Se eliminará "${deleteCat.name}". Sus movimientos pasan a "Sin categoría".` : ''}
        onConfirm={() => {
          if (deleteCat) remove.mutate(deleteCat.id)
          setDeleteCat(null)
        }}
      />
    </div>
  )
}

function Label({ children }: { children: React.ReactNode }) {
  return <div className="cap" style={{ fontSize: 10, letterSpacing: '0.1em', margin: '18px 0 9px' }}>{children}</div>
}

const backLink: CSSProperties = {
  display: 'inline-flex', alignItems: 'center', gap: 4, alignSelf: 'flex-start',
  background: 'none', border: 'none', cursor: 'pointer', font: 'inherit',
  fontSize: 12.5, color: 'var(--color-sage)', padding: 0,
}
const catRow: CSSProperties = {
  display: 'flex', alignItems: 'center', gap: 12, width: '100%',
  padding: '12px 14px', background: 'var(--color-linen)', border: 'none', cursor: 'pointer', font: 'inherit',
}
const emojiTile: CSSProperties = {
  width: 30, height: 30, borderRadius: 9, flexShrink: 0, fontSize: 15,
  display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
}
const bigTile: CSSProperties = {
  width: 52, height: 52, borderRadius: 14, flexShrink: 0, fontSize: 24,
  display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
}
const newRow: CSSProperties = {
  marginTop: 14, width: '100%', textAlign: 'left', border: '1px dashed var(--color-mist)', borderRadius: 14,
  padding: '13px 14px', fontSize: 13, fontWeight: 600, color: 'var(--color-sage)',
  background: 'transparent', cursor: 'pointer', font: 'inherit',
}
const nameInput: CSSProperties = {
  border: '1.6px solid var(--color-obsidian-ink)', borderRadius: 12, padding: '13px 14px',
  fontSize: 14, fontWeight: 500, background: 'var(--color-linen)', color: 'var(--color-obsidian-ink)',
  width: '100%', boxSizing: 'border-box',
}
const context: CSSProperties = {
  marginTop: 18, borderTop: '1px solid var(--color-mist)', paddingTop: 14,
  fontSize: 11.5, lineHeight: 1.5, color: 'var(--color-sage)',
}
const deleteBtn: CSSProperties = {
  border: '1px solid var(--color-mist)', borderRadius: 12, padding: '13px 16px',
  fontSize: 13, fontWeight: 600, color: 'var(--color-error)', background: 'transparent', cursor: 'pointer', font: 'inherit',
}
const saveBtn: CSSProperties = {
  flex: 1, background: 'var(--color-voltage)', color: 'var(--voltage-on-dark)', border: 'none',
  borderRadius: 12, padding: 13, fontSize: 13, fontWeight: 600, cursor: 'pointer', font: 'inherit',
}
const errorStyle: CSSProperties = { fontSize: 12, color: 'var(--color-error)', marginTop: 4, display: 'block' }
