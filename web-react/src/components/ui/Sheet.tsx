import { type ReactNode } from 'react'
export default function Sheet({ title, onClose, children }: { title: string; onClose: () => void; children: ReactNode }) {
  return (
    <div onClick={onClose} style={{ minHeight: 420, position: 'relative', display: 'flex', alignItems: 'flex-end', background: 'rgba(18,22,19,0.45)' }}>
      <div onClick={(e) => e.stopPropagation()} style={{ width: '100%', background: 'var(--color-linen)', borderTopLeftRadius: 18, borderTopRightRadius: 18, padding: 22 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <span style={{ fontSize: 16, fontWeight: 500 }}>{title}</span>
          <button onClick={onClose} aria-label="Cerrar" style={{ background: 'none', border: 'none', cursor: 'pointer' }}>
            <i className="ti ti-x" style={{ fontSize: 20 }} aria-hidden />
          </button>
        </div>
        {children}
      </div>
    </div>
  )
}
