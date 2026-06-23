import * as AlertDialog from '@radix-ui/react-alert-dialog'

export default function ConfirmDialog({ open, onOpenChange, title, description, confirmLabel = 'Borrar', onConfirm }: { open: boolean; onOpenChange: (o: boolean) => void; title: string; description: string; confirmLabel?: string; onConfirm: () => void }) {
  return (
    <AlertDialog.Root open={open} onOpenChange={onOpenChange}>
      <AlertDialog.Portal>
        <AlertDialog.Overlay className="nf-overlay" style={{ position: 'fixed', inset: 0, zIndex: 60, background: 'rgba(18,22,19,0.45)' }} />
        <AlertDialog.Content className="nf-modal" style={{ position: 'fixed', top: '50%', left: '50%', transform: 'translate(-50%, -50%)', zIndex: 61, width: 'min(440px, 92vw)', borderRadius: 16, padding: 22, maxHeight: '88vh', overflowY: 'auto', background: 'var(--color-linen)', boxShadow: '0 8px 40px rgba(18,22,19,0.18)' }}>
          <AlertDialog.Title style={{ fontSize: 16, fontWeight: 500, margin: '0 0 8px' }}>{title}</AlertDialog.Title>
          <AlertDialog.Description style={{ fontSize: 14, color: 'var(--color-sage)', margin: 0 }}>{description}</AlertDialog.Description>
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10, marginTop: 18 }}>
            <AlertDialog.Cancel style={{ background: 'transparent', border: '1px solid var(--color-mist)', borderRadius: 10, padding: '10px 16px', fontSize: 14, cursor: 'pointer' }}>Cancelar</AlertDialog.Cancel>
            <AlertDialog.Action onClick={onConfirm} style={{ background: 'var(--color-voltage)', color: 'var(--voltage-on-dark)', border: 'none', borderRadius: 10, padding: '10px 16px', fontSize: 14, fontWeight: 500, cursor: 'pointer' }}>{confirmLabel}</AlertDialog.Action>
          </div>
        </AlertDialog.Content>
      </AlertDialog.Portal>
    </AlertDialog.Root>
  )
}
