import { type ReactNode } from 'react'
import * as Dialog from '@radix-ui/react-dialog'

export default function Sheet({ open, onClose, title, children }: { open: boolean; onClose: () => void; title: string; children: ReactNode }) {
  return (
    <Dialog.Root open={open} onOpenChange={(o) => { if (!o) onClose() }}>
      <Dialog.Portal>
        <Dialog.Overlay className="nf-overlay" style={{ position: 'fixed', inset: 0, zIndex: 60, background: 'rgba(18,22,19,0.45)' }} />
        <Dialog.Content
          className="nf-sheet"
          onOpenAutoFocus={(e) => e.preventDefault()}
          onPointerDownOutside={(e) => {
            const t = e.target as HTMLElement | null
            if (t && t.closest('[data-radix-popper-content-wrapper],[data-radix-select-viewport],[role="listbox"]')) e.preventDefault()
          }}
          onInteractOutside={(e) => {
            const t = e.target as HTMLElement | null
            if (t && t.closest('[data-radix-popper-content-wrapper],[data-radix-select-viewport],[role="listbox"]')) e.preventDefault()
          }}
          style={{ position: 'fixed', left: 0, right: 0, bottom: 0, zIndex: 61, margin: '0 auto', width: '100%', maxWidth: 480, maxHeight: '88vh', overflowY: 'auto', background: 'var(--color-linen)', borderTopLeftRadius: 18, borderTopRightRadius: 18, padding: 22 }}>
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
