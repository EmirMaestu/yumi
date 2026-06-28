import * as RS from '@radix-ui/react-select'

export interface Opt { value: string; label: string }

// Select estilizado (Radix). Dentro de un modal/sheet, Radix portalea el desplegable
// fuera del Dialog → para que NO cierre el modal al tocar una opción, los guards están
// en Modal.tsx/Sheet.tsx (onPointerDownOutside/onInteractOutside ignoran el popper/listbox).
// onCloseAutoFocus preventDefault evita que al cerrar el foco vuelva al trigger y, en touch,
// lo reabra (el bug de "se reabre al presionarlo abierto").
export default function Select({ value, onValueChange, options, placeholder, ariaLabel, style }: { value?: string; onValueChange: (v: string) => void; options: Opt[]; placeholder?: string; ariaLabel?: string; style?: React.CSSProperties }) {
  return (
    <RS.Root value={value} onValueChange={onValueChange}>
      <RS.Trigger aria-label={ariaLabel} style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'space-between', gap: 8, border: '1px solid var(--color-mist)', borderRadius: 10, padding: '9px 12px', fontSize: 14, background: 'var(--color-linen)', color: 'var(--color-obsidian-ink)', cursor: 'pointer', ...style }}>
        <RS.Value placeholder={placeholder} />
        <RS.Icon><i className="ti ti-chevron-down" style={{ fontSize: 15, color: 'var(--color-sage)' }} aria-hidden /></RS.Icon>
      </RS.Trigger>
      <RS.Portal>
        <RS.Content position="popper" sideOffset={6} className="nf-pop" onCloseAutoFocus={(e) => e.preventDefault()} style={{ background: 'var(--color-linen)', border: '1px solid var(--color-mist)', borderRadius: 12, padding: 6, zIndex: 70, boxShadow: '0 8px 28px rgba(18,22,19,0.14)', minWidth: 'max(var(--radix-select-trigger-width), 180px)' }}>
          <RS.Viewport>
            {options.map((o) => (
              <RS.Item key={o.value} value={o.value} className="nf-item" style={{ fontSize: 14, padding: '9px 12px', paddingRight: 14, borderRadius: 8, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 16 }}>
                <RS.ItemText><span style={{ flex: 1 }}>{o.label}</span></RS.ItemText>
                <RS.ItemIndicator><i className="ti ti-check" style={{ fontSize: 15, color: 'var(--color-voltage)' }} aria-hidden /></RS.ItemIndicator>
              </RS.Item>
            ))}
          </RS.Viewport>
        </RS.Content>
      </RS.Portal>
    </RS.Root>
  )
}
