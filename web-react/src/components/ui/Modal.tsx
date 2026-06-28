import { type ReactNode } from 'react'
import * as Dialog from '@radix-ui/react-dialog'

export default function Modal({ open, onClose, title, children }: { open: boolean; onClose: () => void; title: string; children: ReactNode }) {
  return (
    <Dialog.Root open={open} onOpenChange={(o) => { if (!o) onClose() }}>
      <Dialog.Portal>
        <Dialog.Overlay className="nf-overlay" style={{ position: 'fixed', inset: 0, zIndex: 60, background: 'rgba(18,22,19,0.45)' }} />
        <Dialog.Content
          className="nf-modal"
          onOpenAutoFocus={(e) => e.preventDefault()}
          onPointerDownOutside={(e) => {
            const t = e.target as HTMLElement | null
            if (t && t.closest('[data-radix-popper-content-wrapper],[data-radix-select-viewport],[role="listbox"]')) e.preventDefault()
          }}
          onInteractOutside={(e) => {
            // No cerrar el modal cuando el "afuera" es el desplegable de un Select/dropdown
            // (Radix lo portalea fuera del Dialog → se interpretaba como click afuera).
            const t = e.target as HTMLElement | null
            if (t && t.closest('[data-radix-popper-content-wrapper],[data-radix-select-viewport],[role="listbox"]')) e.preventDefault()
          }}
          style={{ position: 'fixed', top: '50%', left: '50%', transform: 'translate(-50%, -50%)', zIndex: 61, width: 'min(440px, 92vw)', borderRadius: 16, padding: 22, maxHeight: '88vh', overflowY: 'auto', background: 'var(--color-linen)', boxShadow: '0 8px 40px rgba(18,22,19,0.18)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
            <Dialog.Title style={{ fontSize: 16, fontWeight: 500, margin: 0 }}>{title}</Dialog.Title>
            <Dialog.Close aria-label="Cerrar" style={{ background: 'none', border: 'none', cursor: 'pointer' }}><i className="ti ti-x" style={{ fontSize: 20 }} aria-hidden /></Dialog.Close>
          </div>
          {children}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
