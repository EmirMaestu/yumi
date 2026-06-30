import { useRef, useState } from 'react'
import * as RS from '@radix-ui/react-select'
import { radixPopperOpened, radixPopperClosed } from './radixOpenState'

export interface Opt { value: string; label: string }

// Select estilizado (Radix). Dentro de un modal/sheet, Radix portalea el desplegable
// fuera del Dialog → para que NO cierre el modal al tocar una opción, los guards están
// en Modal.tsx/Sheet.tsx (onPointerDownOutside/onInteractOutside ignoran el popper/listbox).
//
// iOS "se reabre al tocar el trigger abierto": al tocar el trigger estando abierto, Radix
// lo cierra (pointerdown afuera) y el mismo tap lo vuelve a abrir (doble-fire táctil).
// Lo controlamos: ignoramos un "abrir" que llega apenas después de un "cerrar".
//
// Categorías largas que se salían de la pantalla → maxHeight (alto disponible) + scroll.
export default function Select({ value, onValueChange, options, placeholder, ariaLabel, style }: { value?: string; onValueChange: (v: string) => void; options: Opt[]; placeholder?: string; ariaLabel?: string; style?: React.CSSProperties }) {
  const [open, setOpen] = useState(false)
  const closedAt = useRef(0)

  function handleOpenChange(next: boolean) {
    if (next && Date.now() - closedAt.current < 350) return // ignora la reapertura espuria post-cierre (iOS)
    if (!next) closedAt.current = Date.now()
    setOpen(next)
    if (next) radixPopperOpened(); else radixPopperClosed()
  }

  return (
    <RS.Root value={value} onValueChange={onValueChange} open={open} onOpenChange={handleOpenChange}>
      <RS.Trigger aria-label={ariaLabel} style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'space-between', gap: 8, border: '1px solid var(--color-mist)', borderRadius: 10, padding: '9px 12px', fontSize: 14, background: 'var(--color-linen)', color: 'var(--color-obsidian-ink)', cursor: 'pointer', ...style }}>
        <RS.Value placeholder={placeholder} />
        <RS.Icon><i className="ti ti-chevron-down" style={{ fontSize: 15, color: 'var(--color-sage)' }} aria-hidden /></RS.Icon>
      </RS.Trigger>
      <RS.Portal>
        {/* maxHeight FIJO (no uso --radix-select-content-available-height: en un sheet bajo
            da negativo y colapsa el desplegable). avoidCollisions lo mantiene en pantalla. */}
        <RS.Content
          position="popper"
          sideOffset={6}
          collisionPadding={10}
          className="nf-pop"
          onCloseAutoFocus={(e) => e.preventDefault()}
          style={{ background: 'var(--color-linen)', border: '1px solid var(--color-mist)', borderRadius: 12, padding: 6, zIndex: 70, boxShadow: '0 8px 28px rgba(18,22,19,0.14)', minWidth: 'max(var(--radix-select-trigger-width), 180px)', maxHeight: 'min(340px, 70vh)', display: 'flex', flexDirection: 'column' }}
        >
          <RS.ScrollUpButton style={scrollBtn}><i className="ti ti-chevron-up" aria-hidden /></RS.ScrollUpButton>
          <RS.Viewport style={{ overflowY: 'auto' }}>
            {options.map((o) => (
              <RS.Item key={o.value} value={o.value} className="nf-item" style={{ fontSize: 14, padding: '9px 12px', paddingRight: 14, borderRadius: 8, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 16 }}>
                <RS.ItemText><span style={{ flex: 1 }}>{o.label}</span></RS.ItemText>
                <RS.ItemIndicator><i className="ti ti-check" style={{ fontSize: 15, color: 'var(--color-voltage)' }} aria-hidden /></RS.ItemIndicator>
              </RS.Item>
            ))}
          </RS.Viewport>
          <RS.ScrollDownButton style={scrollBtn}><i className="ti ti-chevron-down" aria-hidden /></RS.ScrollDownButton>
        </RS.Content>
      </RS.Portal>
    </RS.Root>
  )
}

const scrollBtn: React.CSSProperties = {
  display: 'flex', alignItems: 'center', justifyContent: 'center', height: 22,
  color: 'var(--color-sage)', cursor: 'default',
}
