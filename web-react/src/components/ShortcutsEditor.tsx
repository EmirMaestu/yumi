import { useEffect, useState, type CSSProperties } from 'react'
import Sheet from './ui/Sheet'
import { useMe } from '../hooks/useMe'
import { SHORTCUT_CATALOG, MAX_SHORTCUTS, type ShortcutDef } from '../lib/shortcuts'

// Drawer "Elegí tus atajos" (diseño 1b): togglear qué atajos van al home (hasta 6),
// con los del catálogo que sobran como sugeridos. El orden = orden de selección.
export default function ShortcutsEditor({ open, onClose, ids, onSave }: {
  open: boolean; onClose: () => void; ids: string[]; onSave: (ids: string[]) => void
}) {
  const { data: me } = useMe()
  const partner = me?.others?.[0]?.name
  const [sel, setSel] = useState<string[]>(ids)
  useEffect(() => { if (open) setSel(ids) }, [open, ids])

  const inHome = sel.map((id) => SHORTCUT_CATALOG.find((s) => s.id === id)).filter(Boolean) as ShortcutDef[]
  const suggested = SHORTCUT_CATALOG.filter((s) => !sel.includes(s.id))
  const toggle = (id: string) =>
    setSel((cur) => cur.includes(id) ? cur.filter((x) => x !== id) : (cur.length >= MAX_SHORTCUTS ? cur : [...cur, id]))

  const scopeLabel = (s: ShortcutDef) => s.shareable ? (partner ? `Con ${partner}` : 'Compartido') : 'Solo mío'

  return (
    <Sheet open={open} onClose={onClose} title="Elegí tus atajos">
      <div style={{ display: 'grid', gap: 8 }}>
        <p style={hint}>Hasta {MAX_SHORTCUTS} en el home. Los compartidos aparecen para los dos.</p>

        <div style={sectionCap}>En el home · {inHome.length} de {MAX_SHORTCUTS}</div>
        {inHome.map((s) => (
          <Row key={s.id} s={s} scope={scopeLabel(s)} on onToggle={() => toggle(s.id)} />
        ))}

        {suggested.length > 0 && <div style={{ ...sectionCap, marginTop: 6 }}>Sumar más</div>}
        {suggested.map((s) => (
          <Row key={s.id} s={s} scope={scopeLabel(s)} on={false} dashed onToggle={() => toggle(s.id)} />
        ))}

        <button onClick={() => { onSave(sel); onClose() }} style={cta}>Guardar atajos</button>
      </div>
    </Sheet>
  )
}

function Row({ s, scope, on, dashed, onToggle }: { s: ShortcutDef; scope: string; on: boolean; dashed?: boolean; onToggle: () => void }) {
  return (
    <button type="button" onClick={onToggle} style={{ ...row, border: `1px ${dashed ? 'dashed' : 'solid'} var(--color-mist)` }}>
      <i className={`ti ${s.icon}`} style={{ fontSize: 16, color: 'var(--color-sage)' }} aria-hidden />
      <span style={{ flex: 1, textAlign: 'left', fontSize: 13, fontWeight: 600, color: 'var(--color-obsidian-ink)' }}>{s.label}</span>
      <span style={{ fontSize: 10.5, color: s.shareable ? 'var(--color-voltage-ink, #1f7a2e)' : 'var(--color-sage)' }}>{scope}</span>
      <span aria-hidden style={{ ...toggle, background: on ? 'var(--color-voltage)' : 'var(--color-mist)' }}>
        <span style={{ ...knob, [on ? 'right' : 'left']: 2 }} />
      </span>
    </button>
  )
}

const hint: CSSProperties = { margin: 0, fontSize: 12, color: 'var(--color-sage)', lineHeight: 1.4 }
const sectionCap: CSSProperties = { fontSize: 10, letterSpacing: '.1em', textTransform: 'uppercase', color: 'var(--color-sage)', fontWeight: 600, marginTop: 8 }
const row: CSSProperties = { display: 'flex', alignItems: 'center', gap: 11, width: '100%', borderRadius: 12, padding: '11px 13px', background: 'var(--color-linen)', cursor: 'pointer', font: 'inherit' }
const toggle: CSSProperties = { width: 34, height: 20, borderRadius: 999, position: 'relative', flexShrink: 0, display: 'inline-block' }
const knob: CSSProperties = { position: 'absolute', top: 2, width: 16, height: 16, borderRadius: '50%', background: '#fff' }
const cta: CSSProperties = { marginTop: 10, background: 'var(--color-voltage)', color: 'var(--voltage-on-dark)', border: 'none', borderRadius: 14, padding: 14, fontWeight: 600, fontSize: 14, cursor: 'pointer', font: 'inherit' }
